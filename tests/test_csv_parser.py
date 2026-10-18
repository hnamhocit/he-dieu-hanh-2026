"""Kiểm thử đọc file CSV và kiểm tra dữ liệu đầu vào."""

import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.utils.csv_parser import CSVParser, SimulationStep


HEADER = "id,action,sender,receiver,message,delay_ms,priority\n"


class TestCSVParser(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "scenario.csv"
        self.parser = CSVParser()

    def parse_text(self, text: str, encoding: str = "utf-8") -> list[SimulationStep]:
        self.path.write_text(text, encoding=encoding, newline="")
        return self.parser.parse(self.path)

    def test_repository_sample(self) -> None:
        sample = Path(__file__).resolve().parents[1] / "data/input/sample_messages.csv"
        steps = self.parser.parse(str(sample))
        self.assertEqual(len(steps), 7)
        self.assertEqual(
            steps[0],
            SimulationStep(1, "PRODUCE", "Process_A", "Process_B", "Hello from Process A", 50, 0),
        )
        self.assertEqual(steps[1].message, "")
        self.assertEqual(steps[4].priority, 1)

    def test_all_actions_and_file_order(self) -> None:
        steps = self.parse_text(
            HEADER
            + "4,PRODUCE,P1,C1,hello,0,0\n"
            + "2,CONSUME,C1,P1,,0,0\n"
            + "3,SEND,P2,C2,message,10,2\n"
            + "1,RECEIVE,C2,P2,,0,0\n"
        )
        self.assertEqual([step.id for step in steps], [4, 2, 3, 1])
        self.assertEqual([step.action for step in steps], ["PRODUCE", "CONSUME", "SEND", "RECEIVE"])

    def test_optional_columns_and_header_order(self) -> None:
        steps = self.parse_text("receiver,id,sender,action\nC1,1,P1,PRODUCE\n")
        self.assertEqual(steps, [SimulationStep(1, "PRODUCE", "P1", "C1")])

    def test_empty_optional_cells(self) -> None:
        for row in ("1,SEND,P1,C1,,,\n", "1,SEND,P1,C1,, , \n"):
            with self.subTest(row=row):
                steps = self.parse_text(HEADER + row)
                self.assertEqual(steps, [SimulationStep(1, "SEND", "P1", "C1")])

    def test_bom_unicode_and_quoted_payload(self) -> None:
        message = '  Xin chào, "tiến trình B"!\nDòng thứ hai  '
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(HEADER.strip().split(","))
        writer.writerow([1, "SEND", "P1", "C1", message, 0, 5])
        steps = self.parse_text(stream.getvalue(), encoding="utf-8-sig")
        self.assertEqual(steps[0].message, message)

    def test_whitespace_and_negative_priority(self) -> None:
        steps = self.parse_text(HEADER + " 1 , SEND , P1 , C1 , payload , 5 ,-2\n")
        self.assertEqual(steps, [SimulationStep(1, "SEND", "P1", "C1", " payload ", 5, -2)])

    def test_blank_lines_are_skipped(self) -> None:
        steps = self.parse_text(HEADER + "\n1,PRODUCE,P1,C1,hello,0,0\n\n")
        self.assertEqual(len(steps), 1)

    def test_invalid_field_values(self) -> None:
        cases = [
            ("abc,PRODUCE,P1,C1,hello,0,0\n", "id"),
            ("1.5,PRODUCE,P1,C1,hello,0,0\n", "id"),
            ("0,PRODUCE,P1,C1,hello,0,0\n", "id"),
            ("-1,PRODUCE,P1,C1,hello,0,0\n", "id"),
            (",PRODUCE,P1,C1,hello,0,0\n", "id"),
            ("1,UNKNOWN,P1,C1,hello,0,0\n", "action"),
            ("1,produce,P1,C1,hello,0,0\n", "action"),
            ("1,PRODUCE, ,C1,hello,0,0\n", "sender"),
            ("1,PRODUCE,P1,,hello,0,0\n", "receiver"),
            ("1,PRODUCE,P1,C1,hello,abc,0\n", "delay_ms"),
            ("1,PRODUCE,P1,C1,hello,-1,0\n", "delay_ms"),
            ("1,PRODUCE,P1,C1,hello,0,1.5\n", "priority"),
            ("1,CONSUME,C1,P1,unexpected,0,0\n", "message"),
            ("1,RECEIVE,C1,P1,unexpected,0,0\n", "message"),
        ]
        for row, field in cases:
            with self.subTest(row=row):
                with self.assertRaises(ValueError) as context:
                    self.parse_text(HEADER + row)
                self.assertIn("Dòng 2", str(context.exception))
                self.assertIn(f"'{field}'", str(context.exception))

    def test_duplicate_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "Dòng 3.*ID 1 bị trùng"):
            self.parse_text(HEADER + "1,SEND,P1,C1,a,0,0\n01,SEND,P1,C1,b,0,0\n")

    def test_invalid_second_row_and_retry(self) -> None:
        with self.assertRaisesRegex(ValueError, "Dòng 3.*delay_ms"):
            self.parse_text(HEADER + "1,SEND,P1,C1,a,0,0\n2,SEND,P1,C1,b,bad,0\n")
        # Sửa file rồi đọc lại bằng cùng parser.
        self.assertEqual(len(self.parse_text(HEADER + "1,SEND,P1,C1,a,0,0\n")), 1)

    def test_missing_required_columns(self) -> None:
        for field in CSVParser.REQUIRED_COLUMNS:
            with self.subTest(field=field):
                columns = [name for name in CSVParser.REQUIRED_COLUMNS if name != field]
                with self.assertRaisesRegex(ValueError, f"thiếu cột bắt buộc: {field}"):
                    self.parse_text(",".join(columns) + "\n")

    def test_duplicate_and_unknown_header(self) -> None:
        for header in (
            "id,action,sender,receiver,id\n",
            "id,action,sender,receiver,delay_mss\n",
        ):
            with self.subTest(header=header):
                with self.assertRaises(ValueError):
                    self.parse_text(header)

    def test_record_width_must_match_header(self) -> None:
        for row in ("1,SEND,P1,C1,a,0\n", "1,SEND,P1,C1,a,0,0,extra\n"):
            with self.subTest(row=row):
                with self.assertRaisesRegex(ValueError, "Dòng 2.*không khớp header"):
                    self.parse_text(HEADER + row)

    def test_no_simulation_data(self) -> None:
        for text in ("", "\n", HEADER, HEADER + "\n\n"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    self.parse_text(text)


if __name__ == "__main__":
    unittest.main()
