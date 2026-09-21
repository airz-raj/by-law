"""Extract plain text from uploaded files."""

from __future__ import annotations

import io
from typing import BinaryIO

import pypdf

from app.config import Settings
from app.errors import InputRejected


def extract_text(file_obj: BinaryIO, settings: Settings) -> str:
    """Read a file object and extract UTF-8 text or PDF content.

    Enforces limits on bytes, pages, and extracted characters.
    Rejects encrypted PDFs and files that appear to be scanned PDFs.
    """
    # 1. Read at most max_upload_bytes + 1
    raw = file_obj.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise InputRejected("FILE_TOO_LARGE", "The file exceeds the upload limit.")

    # 2. PDF detection
    is_pdf = raw.startswith(b"%PDF-")

    text = ""
    if is_pdf:
        try:
            reader = pypdf.PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise InputRejected("ENCRYPTED_PDF", "Cannot read a password-protected PDF.")

            num_pages = len(reader.pages)
            if num_pages > settings.max_pdf_pages:
                raise InputRejected("TOO_MANY_PAGES", "The PDF has too many pages.")

            pages_text = []
            for page in reader.pages:
                pt = page.extract_text()
                if pt:
                    pages_text.append(pt)
            text = "\n".join(pages_text)
        except pypdf.errors.PyPdfError as e:
            raise InputRejected("INVALID_PDF", "The file is a corrupted or unreadable PDF.") from e

        # If it's a PDF but text is too short, assume it's scanned
        if len(text.strip()) < settings.min_notice_chars:
            raise InputRejected("SCANNED_PDF", "The PDF appears to be an image. Please use text.")

    else:
        # 3. Plain text decoding
        if b"\x00" in raw:
            raise InputRejected("UNSUPPORTED_TYPE", "Binary files are not supported.")

        try:
            # decode as utf-8, strip BOM if present
            decoded = raw.decode("utf-8-sig")
            text = decoded
        except UnicodeDecodeError as e:
            raise InputRejected(
                "UNSUPPORTED_TYPE",
                "Only UTF-8 text and readable PDFs are supported."
            ) from e

        if len(text.strip()) < settings.min_notice_chars:
            raise InputRejected("TEXT_TOO_SHORT", "The text provided is too short to be a legal notice.")

    # 4. Enforce max document chars limit
    if len(text) > settings.max_document_chars:
        raise InputRejected("DOCUMENT_TOO_LONG", "The document contains too much text.")

    return text
