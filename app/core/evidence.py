"""Confirm model-generated quotes against the source text.

Each quote is located in the original document.  If found, the Receipt
carries the start and end offsets into the *original* (not normalised) text.
"""

from __future__ import annotations

import re
import unicodedata

from app.core.models import Receipt, ReceiptReason

_MIN_QUOTE_LENGTH = 12


def _normalise(text: str) -> str:
    """Normalise text for fuzzy-ish matching.

    Unicode NFKC, lower-case, curly quotes and dashes folded to ASCII,
    all whitespace runs collapsed to one space.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip()


def _build_index_map(original: str, normalised: str) -> list[int]:
    """Build a map from normalised positions back to original positions.

    ``index_map[norm_pos]`` gives the corresponding position in *original*.
    """
    index_map: list[int] = []
    orig_idx = 0
    orig_len = len(original)
    norm_lower = normalised

    for norm_idx in range(len(norm_lower)):
        norm_char = norm_lower[norm_idx]

        if norm_char == " ":
            while orig_idx < orig_len and not original[orig_idx].isspace():
                orig_idx += 1
            index_map.append(orig_idx)
            while orig_idx < orig_len and original[orig_idx].isspace():
                orig_idx += 1
        else:
            while orig_idx < orig_len:
                orig_char = unicodedata.normalize("NFKC", original[orig_idx]).lower()
                orig_char = (
                    orig_char.replace("\u2018", "'")
                    .replace("\u2019", "'")
                    .replace("\u201c", '"')
                    .replace("\u201d", '"')
                    .replace("\u2013", "-")
                    .replace("\u2014", "-")
                )
                if orig_char and orig_char[0] == norm_char:
                    index_map.append(orig_idx)
                    orig_idx += 1
                    break
                orig_idx += 1
            else:
                index_map.append(orig_idx)

    return index_map


def locate(quote: str, source: str) -> Receipt:
    """Locate *quote* in *source* and return a Receipt.

    Quotes shorter than 12 characters after normalisation return
    ``found=False`` with reason ``TOO_SHORT``.

    Matching strategy:
    1. Exact substring match.
    2. Normalised match (NFKC, lower-case, folded punctuation, collapsed
       whitespace) with an index map back to original positions.
    3. Ellipsis fragments: a quote containing ``...`` or ``…`` is split
       into fragments that must all appear in order.

    No fuzzy matching.
    """
    norm_quote = _normalise(quote)

    if len(norm_quote) < _MIN_QUOTE_LENGTH:
        return Receipt(quote=quote, found=False, reason=ReceiptReason.TOO_SHORT)

    # 1. Exact match
    idx = source.find(quote)
    if idx != -1:
        return Receipt(quote=quote, found=True, start=idx, end=idx + len(quote))

    # 2. Normalised match
    norm_source = _normalise(source)
    norm_idx = norm_source.find(norm_quote)
    if norm_idx != -1:
        index_map = _build_index_map(source, norm_source)
        orig_start = index_map[norm_idx] if norm_idx < len(index_map) else 0
        norm_end = norm_idx + len(norm_quote) - 1
        orig_end = (index_map[norm_end] + 1) if norm_end < len(index_map) else len(source)
        return Receipt(quote=quote, found=True, start=orig_start, end=orig_end)

    # 3. Ellipsis fragments
    ellipsis_pat = re.compile(r"\.{3}|…")
    if ellipsis_pat.search(norm_quote):
        fragments = [f.strip() for f in ellipsis_pat.split(norm_quote) if f.strip()]
        if len(fragments) >= 2 and all(len(f) >= 4 for f in fragments):
            search_start = 0
            first_pos: int | None = None
            last_end: int | None = None
            all_found = True

            for fragment in fragments:
                frag_idx = norm_source.find(fragment, search_start)
                if frag_idx == -1:
                    all_found = False
                    break
                if first_pos is None:
                    first_pos = frag_idx
                last_end = frag_idx + len(fragment)
                search_start = last_end

            if all_found and first_pos is not None and last_end is not None:
                index_map = _build_index_map(source, norm_source)
                orig_start = index_map[first_pos] if first_pos < len(index_map) else 0
                orig_end_idx = last_end - 1
                orig_end = (
                    (index_map[orig_end_idx] + 1) if orig_end_idx < len(index_map) else len(source)
                )
                return Receipt(quote=quote, found=True, start=orig_start, end=orig_end)

    return Receipt(quote=quote, found=False, reason=ReceiptReason.NOT_FOUND)
