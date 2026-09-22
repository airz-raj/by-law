"""Structural checks on the page itself.

These run in the Python suite so the build fails on a broken page even
when the Node toolchain is not available.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from itertools import pairwise
from pathlib import Path

import pytest

from tests.paths import WEB_ROOT

INDEX = WEB_ROOT / "index.html"


class Collector(HTMLParser):
    """Collect the parts of the page the tests assert on."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.headings: list[str] = []
        self.inputs: list[dict[str, str]] = []
        self.labels_for: set[str] = set()
        self.inline_styles: list[str] = []
        self.scripts: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: (value or "") for name, value in attrs}
        self.tags.append(tag)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(tag)
        if tag in {"input", "textarea", "select"}:
            self.inputs.append(values)
        if tag == "label" and "for" in values:
            self.labels_for.add(values["for"])
        if "style" in values:
            self.inline_styles.append(tag)
        if tag == "script":
            self.scripts.append(values)
        if tag == "meta":
            self.meta.append(values)
        if tag == "link":
            self.links.append(values)
        if "id" in values:
            self.ids.append(values["id"])


@pytest.fixture(scope="module")
def page() -> Collector:
    collector = Collector()
    collector.feed(INDEX.read_text(encoding="utf-8"))
    return collector


@pytest.fixture(scope="module")
def source() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_the_page_declares_its_language(source: str) -> None:
    assert re.search(r"<html[^>]*\slang=\"en\"", source)


def test_the_page_has_a_title(source: str) -> None:
    title = re.search(r"<title>(.*?)</title>", source, re.DOTALL)
    assert title is not None
    assert "Mohlat" in title.group(1)


def test_the_page_sets_a_viewport(page: Collector) -> None:
    viewports = [m for m in page.meta if m.get("name") == "viewport"]
    assert viewports
    assert "width=device-width" in viewports[0]["content"]


def test_the_page_has_one_h1(page: Collector) -> None:
    assert page.headings.count("h1") == 1


def test_the_page_skips_no_heading_levels(page: Collector) -> None:
    levels = [int(tag[1]) for tag in page.headings]
    for previous, current in pairwise(levels):
        assert current - previous <= 1


def test_the_page_has_the_landmarks(page: Collector) -> None:
    for landmark in ("header", "main", "footer", "nav"):
        assert landmark in page.tags


def test_the_page_starts_with_a_skip_link(source: str) -> None:
    assert 'class="skip-link" href="#main"' in source
    assert 'id="main"' in source


def test_every_control_has_a_label(page: Collector) -> None:
    for control in page.inputs:
        if control.get("type") in {"hidden", "submit", "button"}:
            continue
        identifier = control.get("id", "")
        assert identifier, f"a control has no id: {control}"
        assert identifier in page.labels_for, f"no label for {identifier}"


def test_the_page_has_no_inline_styles(page: Collector) -> None:
    assert page.inline_styles == []


def test_the_page_has_no_inline_script(source: str) -> None:
    """An inline script would force a CSP exception."""
    blocks = re.findall(r"<script\b[^>]*>(.*?)</script>", source, re.DOTALL)
    assert all(block.strip() == "" for block in blocks)


def test_every_script_is_a_module_from_this_origin(page: Collector) -> None:
    assert page.scripts
    for script in page.scripts:
        assert script.get("type") == "module"
        assert script["src"].startswith("/")


def test_every_stylesheet_is_from_this_origin(page: Collector) -> None:
    sheets = [link for link in page.links if link.get("rel") == "stylesheet"]
    assert sheets
    for sheet in sheets:
        assert sheet["href"].startswith("/")


def test_the_page_loads_nothing_from_another_origin(source: str) -> None:
    assert "http://" not in source
    for external in re.findall(r'(?:src|href)="(https?://[^"]+)"', source):
        raise AssertionError(f"the page references {external}")


def test_the_page_carries_the_disclaimer(source: str) -> None:
    assert "not legal advice" in source


def test_the_page_names_the_legal_aid_helpline(source: str) -> None:
    assert "15100" in source


def test_the_ids_the_scripts_need_all_exist(page: Collector) -> None:
    required = {
        "intake",
        "intake-form",
        "intake-heading",
        "error-summary",
        "error-summary-list",
        "notice-text",
        "notice-file",
        "paste-field",
        "file-field",
        "receipt-date",
        "language-select",
        "reading-level",
        "submit-button",
        "progress",
        "report",
        "report-body",
        "contents-list",
        "start-again",
        "source-paste",
        "source-file",
    }
    assert required <= set(page.ids), required - set(page.ids)


def test_every_translatable_string_has_a_key(source: str) -> None:
    """Every data-i18n key on the page exists in both language files."""
    import json

    keys = set(re.findall(r'data-i18n="([^"]+)"', source))
    assert keys
    for code in ("en", "hi"):
        strings = json.loads((WEB_ROOT / "i18n" / f"{code}.json").read_text(encoding="utf-8"))
        missing = keys - set(strings)
        assert not missing, f"{code}.json is missing {sorted(missing)}"


def test_the_samples_the_page_offers_all_exist(source: str) -> None:
    for name in re.findall(r'data-sample="([^"]+)"', source):
        assert (WEB_ROOT / "samples" / f"{name}.txt").exists(), name


def test_the_stylesheets_the_page_loads_all_exist(page: Collector) -> None:
    for link in page.links:
        href = link.get("href", "")
        if href.startswith("/css/"):
            assert (WEB_ROOT / Path(href.lstrip("/"))).exists(), href


def test_the_scripts_the_page_loads_all_exist(page: Collector) -> None:
    for script in page.scripts:
        src = script.get("src", "")
        assert (WEB_ROOT / Path(src.lstrip("/"))).exists(), src
