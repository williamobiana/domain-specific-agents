from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.errors import ConversionError
from src.pdf_converter import (
    _extract_with_pdfminer,
    _extract_with_pdfplumber,
    _write_temp_markdown,
    convert_pdf,
)


def _make_mock_pdf(pages_text: list[str | None]) -> MagicMock:
    """Return a mock pdfplumber PDF context manager with the given per-page text."""
    pages = []
    for text in pages_text:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)
    mock_pdf = MagicMock()
    mock_pdf.pages = pages
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    return mock_pdf


class TestExtractWithPdfplumber:
    def test_returns_text_from_single_page(self):
        mock_pdf = _make_mock_pdf(["Salary £3,500.00"])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = _extract_with_pdfplumber("dummy.pdf")
        assert result == "Salary £3,500.00"

    def test_concatenates_multiple_pages_with_newline(self):
        mock_pdf = _make_mock_pdf(["Page 1 content", "Page 2 content"])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = _extract_with_pdfplumber("dummy.pdf")
        assert "Page 1 content" in result
        assert "Page 2 content" in result
        assert "\n" in result

    def test_skips_pages_with_none_text(self):
        mock_pdf = _make_mock_pdf(["Valid text", None])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = _extract_with_pdfplumber("dummy.pdf")
        assert result == "Valid text"

    def test_returns_none_when_all_pages_return_none(self):
        mock_pdf = _make_mock_pdf([None, None])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = _extract_with_pdfplumber("dummy.pdf")
        assert result is None

    def test_returns_none_when_result_is_whitespace_only(self):
        mock_pdf = _make_mock_pdf(["   \n\t  "])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = _extract_with_pdfplumber("dummy.pdf")
        assert result is None

    def test_returns_none_when_no_pages(self):
        mock_pdf = _make_mock_pdf([])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = _extract_with_pdfplumber("dummy.pdf")
        assert result is None

    def test_returns_none_on_open_exception(self):
        with patch("pdfplumber.open", side_effect=Exception("File not found")):
            result = _extract_with_pdfplumber("nonexistent.pdf")
        assert result is None

    def test_returns_none_on_extract_text_exception(self):
        page = MagicMock()
        page.extract_text.side_effect = Exception("Corrupt page")
        mock_pdf = MagicMock()
        mock_pdf.pages = [page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = _extract_with_pdfplumber("dummy.pdf")
        assert result is None

    def test_passes_pdf_path_to_open(self):
        mock_pdf = _make_mock_pdf(["text"])
        with patch("pdfplumber.open", return_value=mock_pdf) as mock_open:
            _extract_with_pdfplumber("my_expenses.pdf")
            mock_open.assert_called_once_with("my_expenses.pdf")

    def test_skips_pages_with_empty_string(self):
        mock_pdf = _make_mock_pdf(["", "Real content"])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = _extract_with_pdfplumber("dummy.pdf")
        assert result == "Real content"


class TestExtractWithPdfminer:
    def test_returns_text_on_success(self):
        with patch("src.pdf_converter.extract_text", return_value="Salary £3,500.00"):
            result = _extract_with_pdfminer("dummy.pdf")
        assert result == "Salary £3,500.00"

    def test_returns_none_on_empty_string(self):
        with patch("src.pdf_converter.extract_text", return_value=""):
            result = _extract_with_pdfminer("dummy.pdf")
        assert result is None

    def test_returns_none_on_whitespace_only(self):
        with patch("src.pdf_converter.extract_text", return_value="   \n  \t "):
            result = _extract_with_pdfminer("dummy.pdf")
        assert result is None

    def test_returns_none_on_none_result(self):
        with patch("src.pdf_converter.extract_text", return_value=None):
            result = _extract_with_pdfminer("dummy.pdf")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("src.pdf_converter.extract_text", side_effect=Exception("Parse error")):
            result = _extract_with_pdfminer("dummy.pdf")
        assert result is None

    def test_passes_pdf_path_to_extract_text(self):
        with patch("src.pdf_converter.extract_text", return_value="text") as mock_extract:
            _extract_with_pdfminer("my_expenses.pdf")
            mock_extract.assert_called_once_with("my_expenses.pdf")

    def test_multiline_text_preserved(self):
        multiline = "Salary £3,500.00\nRent £900.00"
        with patch("src.pdf_converter.extract_text", return_value=multiline):
            result = _extract_with_pdfminer("dummy.pdf")
        assert result == multiline


class TestWriteTempMarkdown:
    def test_returns_existing_file_path(self):
        path = _write_temp_markdown("some content")
        assert os.path.exists(path)
        os.unlink(path)

    def test_file_has_md_suffix(self):
        path = _write_temp_markdown("some content")
        assert path.endswith(".md")
        os.unlink(path)

    def test_file_is_in_system_temp_dir(self):
        path = _write_temp_markdown("some content")
        assert path.startswith(tempfile.gettempdir())
        os.unlink(path)

    def test_file_contains_exact_content(self):
        content = "Salary £3,500.00\nRent £900.00"
        path = _write_temp_markdown(content)
        with open(path, encoding="utf-8") as f:
            assert f.read() == content
        os.unlink(path)

    def test_file_is_utf8_encoded(self):
        content = "£ € $"
        path = _write_temp_markdown(content)
        with open(path, "rb") as f:
            assert f.read().decode("utf-8") == content
        os.unlink(path)

    def test_empty_content_creates_empty_file(self):
        path = _write_temp_markdown("")
        with open(path, encoding="utf-8") as f:
            assert f.read() == ""
        os.unlink(path)

    def test_each_call_creates_distinct_path(self):
        path1 = _write_temp_markdown("content 1")
        path2 = _write_temp_markdown("content 2")
        assert path1 != path2
        os.unlink(path1)
        os.unlink(path2)


class TestConvertPdf:
    def test_returns_temp_file_path_when_pdfplumber_succeeds(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value="Salary £3,500.00"):
            path = convert_pdf("dummy.pdf")
        assert os.path.exists(path)
        assert path.endswith(".md")
        os.unlink(path)

    def test_fallback_to_pdfminer_when_pdfplumber_returns_none(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value=None):
            with patch("src.pdf_converter._extract_with_pdfminer", return_value="Rent £900.00"):
                path = convert_pdf("dummy.pdf")
        assert os.path.exists(path)
        os.unlink(path)

    def test_raises_conversion_error_when_both_extractors_fail(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value=None):
            with patch("src.pdf_converter._extract_with_pdfminer", return_value=None):
                with pytest.raises(ConversionError):
                    convert_pdf("dummy.pdf")

    def test_conversion_error_message_includes_pdf_path(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value=None):
            with patch("src.pdf_converter._extract_with_pdfminer", return_value=None):
                with pytest.raises(ConversionError, match="my_report.pdf"):
                    convert_pdf("my_report.pdf")

    def test_temp_file_contains_extracted_content(self):
        content = "Salary £3,500.00\nRent £900.00"
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value=content):
            path = convert_pdf("dummy.pdf")
        with open(path, encoding="utf-8") as f:
            assert f.read() == content
        os.unlink(path)

    def test_pdfminer_not_called_when_pdfplumber_succeeds(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value="text"):
            with patch("src.pdf_converter._extract_with_pdfminer") as mock_miner:
                path = convert_pdf("dummy.pdf")
                mock_miner.assert_not_called()
        os.unlink(path)

    def test_pdfplumber_called_with_correct_path(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value="text") as mock_plumber:
            path = convert_pdf("my_expenses.pdf")
            mock_plumber.assert_called_once_with("my_expenses.pdf")
        os.unlink(path)

    def test_pdfminer_called_with_correct_path_on_fallback(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value=None):
            with patch("src.pdf_converter._extract_with_pdfminer", return_value="text") as mock_miner:
                path = convert_pdf("my_expenses.pdf")
                mock_miner.assert_called_once_with("my_expenses.pdf")
        os.unlink(path)

    def test_temp_file_in_system_temp_dir(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value="text"):
            path = convert_pdf("dummy.pdf")
        assert path.startswith(tempfile.gettempdir())
        os.unlink(path)

    def test_raises_conversion_error_type(self):
        with patch("src.pdf_converter._extract_with_pdfplumber", return_value=None):
            with patch("src.pdf_converter._extract_with_pdfminer", return_value=None):
                with pytest.raises(ConversionError) as exc_info:
                    convert_pdf("dummy.pdf")
                assert isinstance(exc_info.value, ConversionError)
