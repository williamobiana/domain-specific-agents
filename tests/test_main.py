from __future__ import annotations

from unittest.mock import patch

import pytest

from src.errors import ConversionError, GroupingError, ParseError
from src.main import main, run_pipeline, validate_paths
from src.parser import ExpenseItem


class TestValidatePaths:
    def test_nonexistent_input_exits_with_code_1(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            validate_paths(str(tmp_path / "missing.pdf"), str(tmp_path / "out.csv"))
        assert exc_info.value.code == 1

    def test_nonexistent_input_prints_to_stderr(self, tmp_path, capsys):
        with pytest.raises(SystemExit):
            validate_paths(str(tmp_path / "missing.pdf"), str(tmp_path / "out.csv"))
        assert "Error" in capsys.readouterr().err

    def test_non_pdf_extension_exits_with_code_1(self, tmp_path):
        txt_file = tmp_path / "file.txt"
        txt_file.write_text("content")
        with pytest.raises(SystemExit) as exc_info:
            validate_paths(str(txt_file), str(tmp_path / "out.csv"))
        assert exc_info.value.code == 1

    def test_non_pdf_extension_prints_to_stderr(self, tmp_path, capsys):
        txt_file = tmp_path / "file.txt"
        txt_file.write_text("content")
        with pytest.raises(SystemExit):
            validate_paths(str(txt_file), str(tmp_path / "out.csv"))
        assert "Error" in capsys.readouterr().err

    def test_nonexistent_output_dir_exits_with_code_1(self, tmp_path):
        pdf_file = tmp_path / "file.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        with pytest.raises(SystemExit) as exc_info:
            validate_paths(str(pdf_file), str(tmp_path / "no_such_dir" / "out.csv"))
        assert exc_info.value.code == 1

    def test_nonexistent_output_dir_prints_to_stderr(self, tmp_path, capsys):
        pdf_file = tmp_path / "file.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        with pytest.raises(SystemExit):
            validate_paths(str(pdf_file), str(tmp_path / "no_such_dir" / "out.csv"))
        assert "Error" in capsys.readouterr().err

    def test_valid_paths_does_not_exit(self, tmp_path):
        pdf_file = tmp_path / "file.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        # Should complete without raising SystemExit
        validate_paths(str(pdf_file), str(tmp_path / "out.csv"))

    def test_pdf_extension_case_insensitive(self, tmp_path):
        pdf_file = tmp_path / "FILE.PDF"
        pdf_file.write_bytes(b"%PDF-1.4")
        validate_paths(str(pdf_file), str(tmp_path / "out.csv"))

    def test_directory_as_input_exits(self, tmp_path):
        subdir = tmp_path / "subdir.pdf"
        subdir.mkdir()
        with pytest.raises(SystemExit) as exc_info:
            validate_paths(str(subdir), str(tmp_path / "out.csv"))
        assert exc_info.value.code == 1


class TestRunPipeline:
    def test_happy_path_returns_empty_unmatched_list(self, tmp_path):
        temp_md = tmp_path / "temp.md"
        temp_md.write_text("Salary £3,500.00\n", encoding="utf-8")
        output_csv = tmp_path / "out.csv"

        with patch("src.main.convert_pdf", return_value=str(temp_md)):
            unmatched = run_pipeline("input.pdf", str(output_csv))

        assert unmatched == []

    def test_temp_file_deleted_on_success(self, tmp_path):
        temp_md = tmp_path / "temp.md"
        temp_md.write_text("Salary £3,500.00\n", encoding="utf-8")
        output_csv = tmp_path / "out.csv"

        with patch("src.main.convert_pdf", return_value=str(temp_md)):
            run_pipeline("input.pdf", str(output_csv))

        assert not temp_md.exists()

    def test_temp_file_deleted_on_parse_error(self, tmp_path):
        temp_md = tmp_path / "temp.md"
        temp_md.write_text("no amounts here\n", encoding="utf-8")
        output_csv = tmp_path / "out.csv"

        with patch("src.main.convert_pdf", return_value=str(temp_md)):
            with pytest.raises(ParseError):
                run_pipeline("input.pdf", str(output_csv))

        assert not temp_md.exists()

    def test_returns_unmatched_items(self, tmp_path):
        temp_md = tmp_path / "temp.md"
        temp_md.write_text("Salary £3,500.00\nunknown item xyz £50.00\n", encoding="utf-8")
        output_csv = tmp_path / "out.csv"

        with patch("src.main.convert_pdf", return_value=str(temp_md)):
            unmatched = run_pipeline("input.pdf", str(output_csv))

        assert len(unmatched) == 1
        assert unmatched[0].raw_text == "unknown item xyz"
        assert unmatched[0].amount == 50.0

    def test_raises_conversion_error_from_convert_pdf(self, tmp_path):
        output_csv = tmp_path / "out.csv"
        with patch("src.main.convert_pdf", side_effect=ConversionError("cannot read")):
            with pytest.raises(ConversionError):
                run_pipeline("bad.pdf", str(output_csv))

    def test_output_csv_created_on_success(self, tmp_path):
        temp_md = tmp_path / "temp.md"
        temp_md.write_text("Salary £3,500.00\n", encoding="utf-8")
        output_csv = tmp_path / "out.csv"

        with patch("src.main.convert_pdf", return_value=str(temp_md)):
            run_pipeline("input.pdf", str(output_csv))

        assert output_csv.exists()

    def test_multiple_items_all_matched(self, tmp_path):
        temp_md = tmp_path / "temp.md"
        temp_md.write_text("Salary £3,500.00\nRent £900.00\n", encoding="utf-8")
        output_csv = tmp_path / "out.csv"

        with patch("src.main.convert_pdf", return_value=str(temp_md)):
            unmatched = run_pipeline("input.pdf", str(output_csv))

        assert unmatched == []


class TestMain:
    def test_exits_zero_on_success(self, tmp_path):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", return_value=[]):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0

    def test_exits_one_on_conversion_error(self, tmp_path):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", side_effect=ConversionError("cannot read")):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1

    def test_exits_one_on_parse_error(self, tmp_path):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", side_effect=ParseError("no items")):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1

    def test_exits_one_on_grouping_error(self, tmp_path):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", side_effect=GroupingError("bad structure")):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1

    def test_exits_one_on_os_error(self, tmp_path):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", side_effect=OSError("permission denied")):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1

    def test_prints_warning_for_unmatched_items(self, tmp_path, capsys):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"
        unmatched = [
            ExpenseItem(raw_text="Misc refund", amount=12.50),
            ExpenseItem(raw_text="TfL", amount=4.80),
        ]

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", return_value=unmatched):
                with pytest.raises(SystemExit):
                    main()

        err = capsys.readouterr().err
        assert "Warning" in err
        assert "2 item(s)" in err
        assert "Misc refund" in err
        assert "TfL" in err

    def test_no_warning_when_all_matched(self, tmp_path, capsys):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", return_value=[]):
                with pytest.raises(SystemExit):
                    main()

        assert "Warning" not in capsys.readouterr().err

    def test_conversion_error_message_printed_to_stderr(self, tmp_path, capsys):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", side_effect=ConversionError("bad pdf")):
                with pytest.raises(SystemExit):
                    main()

        assert "Error" in capsys.readouterr().err

    def test_parse_error_message_printed_to_stderr(self, tmp_path, capsys):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", side_effect=ParseError("no items")):
                with pytest.raises(SystemExit):
                    main()

        assert "Error" in capsys.readouterr().err

    def test_exits_one_on_missing_input_file(self, tmp_path):
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(tmp_path / "missing.pdf"), str(output_csv)]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    def test_exits_one_on_non_pdf_input(self, tmp_path):
        txt_file = tmp_path / "report.txt"
        txt_file.write_text("content")
        output_csv = tmp_path / "out.csv"

        with patch("sys.argv", ["expense-summary", str(txt_file), str(output_csv)]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    def test_warning_includes_amount_for_each_unmatched_item(self, tmp_path, capsys):
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        output_csv = tmp_path / "out.csv"
        unmatched = [ExpenseItem(raw_text="Mystery item", amount=99.99)]

        with patch("sys.argv", ["expense-summary", str(pdf_file), str(output_csv)]):
            with patch("src.main.run_pipeline", return_value=unmatched):
                with pytest.raises(SystemExit):
                    main()

        err = capsys.readouterr().err
        assert "Mystery item" in err
        assert "99.99" in err
