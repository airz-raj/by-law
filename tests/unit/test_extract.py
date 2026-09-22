import io

import pytest

from app.adapters.extract import extract_text
from app.errors import InputRejected
from tests.conftest import make_settings


@pytest.fixture
def settings():
    return make_settings(
        max_upload_bytes=10000,
        max_pdf_pages=5,
        min_notice_chars=10,
        max_document_chars=5000,
    )


def test_extract_text_too_large(settings):
    # File is larger than max_upload_bytes
    data = b"x" * 10001
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "FILE_TOO_LARGE"


def test_extract_text_valid_utf8(settings):
    data = b"This is a valid legal notice. Please vacate the premises."
    file_obj = io.BytesIO(data)
    text = extract_text(file_obj, settings)
    assert text == "This is a valid legal notice. Please vacate the premises."


def test_extract_text_too_short(settings):
    data = b"Short"
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "TEXT_TOO_SHORT"


def test_extract_text_invalid_binary(settings):
    data = b"Some text \x00 binary"
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "UNSUPPORTED_TYPE"


def test_extract_text_document_too_long(settings):
    # Valid UTF-8 but longer than max_document_chars
    data = ("Valid text " * 500).encode("utf-8")
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "DOCUMENT_TOO_LONG"


class MockPage:
    def extract_text(self):
        return "This is a valid legal notice text from PDF."


class MockReader:
    def __init__(self, stream):
        self.is_encrypted = False
        self.pages = [MockPage(), MockPage()]


def test_extract_pdf_success(settings, monkeypatch):
    monkeypatch.setattr("pypdf.PdfReader", lambda stream: MockReader(stream))
    data = b"%PDF-1.4 mock pdf data"
    file_obj = io.BytesIO(data)
    text = extract_text(file_obj, settings)
    assert "This is a valid legal notice text from PDF." in text


class MockEncryptedReader:
    def __init__(self, stream):
        self.is_encrypted = True


def test_extract_pdf_encrypted(settings, monkeypatch):
    monkeypatch.setattr("pypdf.PdfReader", lambda stream: MockEncryptedReader(stream))
    data = b"%PDF-1.4 mock pdf data"
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "ENCRYPTED_PDF"


class MockTooManyPagesReader:
    def __init__(self, stream):
        self.is_encrypted = False
        self.pages = [MockPage()] * 10


def test_extract_pdf_too_many_pages(settings, monkeypatch):
    monkeypatch.setattr("pypdf.PdfReader", lambda stream: MockTooManyPagesReader(stream))
    data = b"%PDF-1.4 mock pdf data"
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "TOO_MANY_PAGES"


class MockScannedReader:
    def __init__(self, stream):
        self.is_encrypted = False
        self.pages = []  # No text extracted


def test_extract_pdf_scanned(settings, monkeypatch):
    monkeypatch.setattr("pypdf.PdfReader", lambda stream: MockScannedReader(stream))
    data = b"%PDF-1.4 mock pdf data"
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "SCANNED_PDF"


def test_extract_pdf_corrupted(settings, monkeypatch):
    import pypdf

    def mock_init(stream):
        raise pypdf.errors.PyPdfError("Corrupt")

    monkeypatch.setattr("pypdf.PdfReader", mock_init)
    data = b"%PDF-1.4 bad data"
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "INVALID_PDF"


def test_extract_text_invalid_utf8(settings):
    data = b"\xff\xfe\xff"
    file_obj = io.BytesIO(data)
    with pytest.raises(InputRejected) as exc:
        extract_text(file_obj, settings)
    assert exc.value.code == "UNSUPPORTED_TYPE"
