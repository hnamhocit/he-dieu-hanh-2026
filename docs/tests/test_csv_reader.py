"""Kiểm tra đọc CSV và trả lỗi an toàn; chạy bằng unittest hoặc pytest."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.utils.csv_reader import read_messages


HEADER = "id,action,sender,receiver,message,delay_ms,priority\n"
VALID_ROW = "1,PRODUCE,P1,C1,Hello,50,0\n"


class TestCSVReader(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "messages.csv"

    def read_text(self, content: str, encoding: str = "utf-8") -> dict:
        self.path.write_text(content, encoding=encoding, newline="")
        return read_messages(self.path)

    def assert_error(self, result: dict, code: str) -> None:
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], code)
        self.assertTrue(result["detail"])
        self.assertEqual(result["data"], [])

    def test_empty_files(self) -> None:
        for content in ("", "\n \t\n", "\ufeff", HEADER, HEADER + "\n  \n"):
            with self.subTest(content=content):
                self.assert_error(self.read_text(content), "EMPTY_FILE")

    def test_missing_required_headers(self) -> None:
        columns = HEADER.strip().split(",")
        for missing in ("id", "action", "sender", "receiver"):
            with self.subTest(column=missing):
                header = ",".join(name for name in columns if name != missing)
                result = self.read_text(header + "\n")
                self.assert_error(result, "MISSING_COLUMN")
                self.assertIn(missing, result["detail"])

    def test_short_row_reports_missing_cell(self) -> None:
        result = self.read_text(HEADER + "1,PRODUCE,P1,C1,Hello,50\n")
        self.assert_error(result, "MISSING_COLUMN")
        self.assertIn("priority", result["detail"])
        self.assertIn("Dòng 2", result["detail"])

    def test_extra_cell(self) -> None:
        result = self.read_text(HEADER + VALID_ROW.rstrip() + ",extra\n")
        self.assert_error(result, "INVALID_CSV")

    def test_invalid_numbers_report_column_and_line(self) -> None:
        for column, index in (("id", 0), ("delay_ms", 5), ("priority", 6)):
            for value in ("abc", "1.5", "NaN", "inf"):
                with self.subTest(column=column, value=value):
                    cells = VALID_ROW.strip().split(",")
                    cells[index] = value
                    result = self.read_text(HEADER + ",".join(cells) + "\n")
                    self.assert_error(result, "INVALID_NUMBER")
                    self.assertIn(column, result["detail"])
                    self.assertIn("Dòng 2", result["detail"])
                    self.assertIn(value, result["detail"])

    def test_empty_id_is_invalid_number(self) -> None:
        result = self.read_text(HEADER + ",PRODUCE,P1,C1,Hello,50,0\n")
        self.assert_error(result, "INVALID_NUMBER")

    def test_absent_optional_columns_have_defaults(self) -> None:
        result = self.read_text("id,action,sender,receiver\n1,CONSUME,C1,P1\n")
        self.assertTrue(result["success"])
        row = result["data"][0]
        self.assertEqual(row["message"], "")
        self.assertEqual(row["delay_ms"], 0)
        self.assertEqual(row["priority"], 0)

    def test_blank_optional_numbers_have_defaults(self) -> None:
        result = self.read_text(HEADER + "1,CONSUME,C1,P1,,, \n")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"][0]["delay_ms"], 0)
        self.assertEqual(result["data"][0]["priority"], 0)

    def test_no_partial_data_after_invalid_row(self) -> None:
        result = self.read_text(HEADER + VALID_ROW + "abc,CONSUME,C1,P1,,0,0\n")
        self.assert_error(result, "INVALID_NUMBER")
        self.assertIn("Dòng 3", result["detail"])

    def test_can_read_valid_file_after_error(self) -> None:
        self.assert_error(self.read_text(""), "EMPTY_FILE")
        result = self.read_text(HEADER + VALID_ROW)
        self.assertTrue(result["success"])
        self.assertEqual(result["error_code"], "OK")
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], 1)
        self.assertEqual(result["data"][0]["delay_ms"], 50)

    def test_bom_unicode_and_quoted_multiline_message(self) -> None:
        result = self.read_text(
            HEADER + '1,PRODUCE,P1,C1,"Xin chào, bạn\nDòng hai",50,0\n',
            encoding="utf-8-sig",
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"][0]["message"], "Xin chào, bạn\nDòng hai")

    def test_blank_lines_are_ignored(self) -> None:
        result = self.read_text("\n  \n" + HEADER + "\n  \n" + VALID_ROW + "\n")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data"]), 1)

    def test_bad_headers(self) -> None:
        for header in (HEADER.rstrip() + ",id\n", HEADER.rstrip() + ",\n"):
            with self.subTest(header=header):
                self.assert_error(self.read_text(header), "INVALID_CSV")

    def test_malformed_csv(self) -> None:
        result = self.read_text(HEADER + '1,PRODUCE,P1,C1,"unterminated,50,0\n')
        self.assert_error(result, "INVALID_CSV")

    def test_invalid_encoding(self) -> None:
        self.path.write_bytes(b"\xff\xfe\xff")
        self.assert_error(read_messages(self.path), "FILE_READ_ERROR")

    def test_file_not_found(self) -> None:
        self.assert_error(read_messages(self.path), "FILE_READ_ERROR")

    def test_permission_denied(self) -> None:
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            self.assert_error(read_messages(self.path), "FILE_READ_ERROR")

    def test_repository_sample(self) -> None:
        sample = Path(__file__).resolve().parents[1] / "data/input/sample_messages.csv"
        result = read_messages(sample)
        self.assertTrue(result["success"], result["detail"])
        self.assertEqual(len(result["data"]), 10)
        self.assertEqual(result["data"][0]["message"], "Hello from Process A")
        self.assertEqual(result["data"][1]["message"], "")


if __name__ == "__main__":
    unittest.main()
