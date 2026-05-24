from __future__ import annotations

import os
import tempfile

import pdfplumber
from pdfminer.high_level import extract_text

from src.errors import ConversionError


def _extract_with_pdfplumber(pdf_path: str) -> str | None:
    """Return text extracted by pdfplumber, or None if extraction yields no usable content."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            parts = [text for page in pdf.pages if (text := page.extract_text())]
        result = "\n".join(parts)
    except Exception:
        return None
    return result if result.strip() else None


def _extract_with_pdfminer(pdf_path: str) -> str | None:
    """Return text extracted by pdfminer.six (fallback), or None on failure."""
    try:
        result = extract_text(pdf_path)
    except Exception:
        return None
    return result if result and result.strip() else None


def _write_temp_markdown(content: str) -> str:
    """Write content to a temp file; return the temp file path."""
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def convert_pdf(pdf_path: str) -> str:
    """Extract text from PDF, write to a temp Markdown file, and return the temp file path.
    Raises ConversionError if neither pdfplumber nor pdfminer.six produces usable text."""
    content = _extract_with_pdfplumber(pdf_path)
    if content is None:
        content = _extract_with_pdfminer(pdf_path)
    if content is None:
        raise ConversionError(f"Could not extract usable text from: {pdf_path}")
    return _write_temp_markdown(content)
