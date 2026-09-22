"""Validate an upload and turn it into text.

The file type is decided by the bytes, not the name. PDF support is
imported only when a PDF actually arrives, so the common path never pays
for it. Extraction stops as soon as the text exceeds the document limit,
so a small file that decompresses to a huge one is refused rather than
expanded in full first.
"""

from __future__ import annotations

import io
from typing import BinaryIO

from app.config import Settings
from app.errors import InputRejected

PDF_MAGIC = b"%PDF-"
NUL = b"\x00"

CODE_FILE_TOO_LARGE = "FILE_TOO_LARGE"
CODE_ENCRYPTED_PDF = "ENCRYPTED_PDF"
CODE_TOO_MANY_PAGES = "TOO_MANY_PAGES"
CODE_INVALID_PDF = "INVALID_PDF"
CODE_SCANNED_PDF = "SCANNED_PDF"
CODE_UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
CODE_TEXT_TOO_SHORT = "TEXT_TOO_SHORT"
CODE_DOCUMENT_TOO_LONG = "DOCUMENT_TOO_LONG"


def _read_within_limit(data: BinaryIO, settings: Settings) -> bytes:
    """Read at most one byte more than the limit, so oversize is detectable.

    Raises:
        InputRejected: The upload is larger than the limit.
    """
    raw = data.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise InputRejected(
            CODE_FILE_TOO_LARGE,
            f"That file is larger than the {settings.max_upload_bytes // 1_000_000} MB limit.",
        )
    return raw


def _extract_pdf(raw: bytes, settings: Settings) -> str:
    """Extract text from PDF bytes, stopping at the document limit.

    Raises:
        InputRejected: The PDF is encrypted, unreadable, too long, or holds
            no selectable text.
    """
    import pypdf  # Imported here so a text upload never loads the PDF stack.

    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise InputRejected(
                CODE_ENCRYPTED_PDF,
                "That PDF is password-protected, so it cannot be read. Paste the text instead.",
            )
        if len(reader.pages) > settings.max_pdf_pages:
            raise InputRejected(
                CODE_TOO_MANY_PAGES,
                f"That PDF has more than {settings.max_pdf_pages} pages.",
            )

        pages: list[str] = []
        total = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            total += len(text)
            pages.append(text)
            if total > settings.max_document_chars:
                # Stop here rather than expanding the rest of the file.
                raise InputRejected(
                    CODE_DOCUMENT_TOO_LONG,
                    "That document holds more text than Mohlat reads in one go.",
                )
    except pypdf.errors.PyPdfError as error:
        raise InputRejected(
            CODE_INVALID_PDF, "That PDF could not be opened. It may be damaged."
        ) from error

    joined = "\n".join(pages)
    if len(joined.strip()) < settings.min_notice_chars:
        raise InputRejected(
            CODE_SCANNED_PDF,
            "That PDF looks like a scan, so there is no text to read. Paste the text instead.",
        )
    return joined


def _decode_text(raw: bytes, settings: Settings) -> str:
    """Decode plain-text bytes as UTF-8.

    Raises:
        InputRejected: The bytes are binary, not UTF-8, or too short.
    """
    if NUL in raw:
        raise InputRejected(
            CODE_UNSUPPORTED_TYPE,
            "That looks like a binary file. Send plain text or a PDF with selectable text.",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InputRejected(
            CODE_UNSUPPORTED_TYPE,
            "That file is not plain text or a readable PDF.",
        ) from error

    if len(text.strip()) < settings.min_notice_chars:
        raise InputRejected(
            CODE_TEXT_TOO_SHORT,
            "That is too short to be a notice. Paste the whole document.",
        )
    return text


def extract_text(data: BinaryIO, settings: Settings) -> str:
    """Return the text of an upload, or say why it cannot be read.

    Args:
        data: The uploaded bytes.
        settings: Supplies every limit applied here.

    Returns:
        The extracted text.

    Raises:
        InputRejected: The upload was too large, the wrong type, encrypted,
            scanned, too long, or too short to be a notice.
    """
    raw = _read_within_limit(data, settings)
    text = _extract_pdf(raw, settings) if raw.startswith(PDF_MAGIC) else _decode_text(raw, settings)

    if len(text) > settings.max_document_chars:
        raise InputRejected(
            CODE_DOCUMENT_TOO_LONG,
            "That document holds more text than Mohlat reads in one go.",
        )
    return text
