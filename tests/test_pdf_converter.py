from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.errors import ConversionError
from src.pdf_converter import _convert_with_pdf2docx, _docx_has_content, convert_pdf


def _fake_pdf2docx(converter_mock):
    """Return a fake pdf2docx module with the given Converter mock."""
    module = MagicMock()
    module.Converter = converter_mock
    return module


class TestConvertWithPdf2docx:
    def test_returns_true_on_success(self):
        mock_cv = MagicMock()
        fake_mod = _fake_pdf2docx(MagicMock(return_value=mock_cv))
        with patch.dict(sys.modules, {"pdf2docx": fake_mod}):
            result = _convert_with_pdf2docx("input.pdf", "output.docx")
        assert result is True

    def test_calls_convert_with_correct_args(self):
        mock_cv = MagicMock()
        fake_mod = _fake_pdf2docx(MagicMock(return_value=mock_cv))
        with patch.dict(sys.modules, {"pdf2docx": fake_mod}):
            _convert_with_pdf2docx("input.pdf", "output.docx")
        mock_cv.convert.assert_called_once_with("output.docx", start=0, end=None)

    def test_calls_close_after_convert(self):
        mock_cv = MagicMock()
        fake_mod = _fake_pdf2docx(MagicMock(return_value=mock_cv))
        with patch.dict(sys.modules, {"pdf2docx": fake_mod}):
            _convert_with_pdf2docx("input.pdf", "output.docx")
        mock_cv.close.assert_called_once()

    def test_returns_false_when_converter_raises(self):
        fake_mod = _fake_pdf2docx(MagicMock(side_effect=Exception("corrupt")))
        with patch.dict(sys.modules, {"pdf2docx": fake_mod}):
            result = _convert_with_pdf2docx("bad.pdf", "output.docx")
        assert result is False

    def test_returns_false_when_convert_raises(self):
        mock_cv = MagicMock()
        mock_cv.convert.side_effect = Exception("conversion failed")
        fake_mod = _fake_pdf2docx(MagicMock(return_value=mock_cv))
        with patch.dict(sys.modules, {"pdf2docx": fake_mod}):
            result = _convert_with_pdf2docx("input.pdf", "output.docx")
        assert result is False


class TestDocxHasContent:
    def _make_mock_doc(self, table_texts=None, para_texts=None):
        doc = MagicMock()
        tables = []
        for row_texts in (table_texts or []):
            cells = [MagicMock(text=t) for t in row_texts]
            row = MagicMock(cells=cells)
            table = MagicMock(rows=[row])
            tables.append(table)
        doc.tables = tables
        doc.paragraphs = [MagicMock(text=t) for t in (para_texts or [])]
        return doc

    def test_returns_true_when_table_cell_has_text(self):
        mock_doc = self._make_mock_doc(table_texts=[["Description", "Amount"]])
        with patch("docx.Document", return_value=mock_doc):
            assert _docx_has_content("file.docx") is True

    def test_returns_true_when_paragraph_has_text(self):
        mock_doc = self._make_mock_doc(para_texts=["Salary 3500.00"])
        with patch("docx.Document", return_value=mock_doc):
            assert _docx_has_content("file.docx") is True

    def test_returns_false_when_all_empty(self):
        mock_doc = self._make_mock_doc(table_texts=[[""]], para_texts=[""])
        with patch("docx.Document", return_value=mock_doc):
            assert _docx_has_content("file.docx") is False

    def test_returns_false_on_exception(self):
        with patch("docx.Document", side_effect=Exception("bad file")):
            assert _docx_has_content("file.docx") is False

    def test_whitespace_only_paragraph_returns_false(self):
        mock_doc = self._make_mock_doc(para_texts=["   \n  "])
        with patch("docx.Document", return_value=mock_doc):
            assert _docx_has_content("file.docx") is False


class TestConvertPdf:
    def test_returns_docx_path_on_success(self):
        with patch("src.pdf_converter._convert_with_pdf2docx", return_value=True):
            with patch("src.pdf_converter._docx_has_content", return_value=True):
                path = convert_pdf("input.pdf")
        assert path.endswith(".docx")
        if os.path.exists(path):
            os.unlink(path)

    def test_temp_file_in_system_temp_dir(self):
        with patch("src.pdf_converter._convert_with_pdf2docx", return_value=True):
            with patch("src.pdf_converter._docx_has_content", return_value=True):
                path = convert_pdf("input.pdf")
        assert path.startswith(tempfile.gettempdir())
        if os.path.exists(path):
            os.unlink(path)

    def test_raises_conversion_error_when_convert_fails(self):
        with patch("src.pdf_converter._convert_with_pdf2docx", return_value=False):
            with pytest.raises(ConversionError):
                convert_pdf("input.pdf")

    def test_raises_conversion_error_when_empty_document(self):
        with patch("src.pdf_converter._convert_with_pdf2docx", return_value=True):
            with patch("src.pdf_converter._docx_has_content", return_value=False):
                with pytest.raises(ConversionError):
                    convert_pdf("input.pdf")

    def test_conversion_error_message_contains_pdf_path(self):
        with patch("src.pdf_converter._convert_with_pdf2docx", return_value=False):
            with pytest.raises(ConversionError, match="my_report.pdf"):
                convert_pdf("my_report.pdf")

    def test_empty_document_error_message_contains_pdf_path(self):
        with patch("src.pdf_converter._convert_with_pdf2docx", return_value=True):
            with patch("src.pdf_converter._docx_has_content", return_value=False):
                with pytest.raises(ConversionError, match="input.pdf"):
                    convert_pdf("input.pdf")

    def test_convert_called_with_correct_pdf_path(self):
        with patch("src.pdf_converter._convert_with_pdf2docx", return_value=True) as mock_convert:
            with patch("src.pdf_converter._docx_has_content", return_value=True):
                path = convert_pdf("expenses.pdf")
        assert mock_convert.call_args[0][0] == "expenses.pdf"
        if os.path.exists(path):
            os.unlink(path)

    def test_temp_file_cleaned_up_on_conversion_failure(self):
        import tempfile as _real_tmp
        real_mkstemp = _real_tmp.mkstemp  # capture before patch to avoid recursion
        created_paths = []

        def fake_mkstemp(suffix):
            fd, path = real_mkstemp(suffix=suffix)
            created_paths.append(path)
            return fd, path

        with patch("src.pdf_converter.tempfile.mkstemp", side_effect=fake_mkstemp):
            with patch("src.pdf_converter._convert_with_pdf2docx", return_value=False):
                with pytest.raises(ConversionError):
                    convert_pdf("input.pdf")

        for p in created_paths:
            assert not os.path.exists(p)
