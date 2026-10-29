"""Đọc file kịch bản CSV theo định dạng trong README."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SimulationStep:
    """Dữ liệu của một bước mô phỏng."""

    id: int
    action: str
    sender: str
    receiver: str
    message: str = ""
    delay_ms: int = 0
    priority: int = 0
    simulate_error: str = "NONE"


class CSVParser:
    """Đọc và kiểm tra dữ liệu CSV. Quy tắc các trường nằm ở README mục 6.1."""

    REQUIRED_COLUMNS = ("id", "action", "sender", "receiver")
    OPTIONAL_COLUMNS = ("message", "delay_ms", "priority", "simulate_error")
    ACTIONS = frozenset({"PRODUCE", "CONSUME", "SEND", "RECEIVE"})

    def parse(self, file_path: str | Path) -> list[SimulationStep]:
        """Trả về các bước theo thứ tự trong file; dữ liệu sai gây ValueError."""
        steps: list[SimulationStep] = []
        seen_ids: set[int] = set()

        # utf-8-sig đọc được cả file có BOM xuất từ Excel.
        with Path(file_path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            self._validate_header(reader.fieldnames)

            for row in reader:
                # Message nhiều dòng thì báo số dòng cuối của bản ghi.
                line = reader.line_num
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(
                        f"Dòng {line}: số trường dữ liệu không khớp header."
                    )

                step = self._parse_row(row, line)
                if step.id in seen_ids:
                    raise ValueError(f"Dòng {line}, cột 'id': ID {step.id} bị trùng.")
                seen_ids.add(step.id)
                steps.append(step)

        if not steps:
            raise ValueError("File CSV không có dòng dữ liệu mô phỏng.")
        return steps

    def _validate_header(self, columns: list[str] | None) -> None:
        if not columns:
            raise ValueError("File CSV rỗng hoặc thiếu header.")
        if len(columns) != len(set(columns)):
            raise ValueError("Header CSV có tên cột bị trùng.")

        missing = set(self.REQUIRED_COLUMNS) - set(columns)
        if missing:
            raise ValueError(f"Header CSV thiếu cột bắt buộc: {', '.join(sorted(missing))}.")

        unknown = set(columns) - set(self.REQUIRED_COLUMNS + self.OPTIONAL_COLUMNS)
        if unknown:
            raise ValueError(f"Header CSV có cột không hỗ trợ: {', '.join(sorted(unknown))}.")

    def _parse_row(self, row: dict[str, str], line: int) -> SimulationStep:
        action = row["action"].strip()
        if action not in self.ACTIONS:
            raise ValueError(
                f"Dòng {line}, cột 'action': phải là PRODUCE, CONSUME, SEND hoặc RECEIVE."
            )

        sender = row["sender"].strip()
        receiver = row["receiver"].strip()
        for field, value in (("sender", sender), ("receiver", receiver)):
            if not value:
                raise ValueError(f"Dòng {line}, cột '{field}': không được để trống.")

        # Giữ nguyên khoảng trắng trong nội dung tin nhắn.
        message = row.get("message", "")
        if action in {"CONSUME", "RECEIVE"} and message != "":
            raise ValueError(
                f"Dòng {line}, cột 'message': phải để trống khi action là {action}."
            )

        step_id = self._parse_int(row["id"], "id", line)
        if step_id <= 0:
            raise ValueError(f"Dòng {line}, cột 'id': phải lớn hơn 0.")

        delay_ms = self._parse_int(row.get("delay_ms", "").strip() or "0", "delay_ms", line)
        if delay_ms < 0:
            raise ValueError(f"Dòng {line}, cột 'delay_ms': không được âm.")

        priority = self._parse_int(row.get("priority", "").strip() or "0", "priority", line)
        simulate_error = row.get("simulate_error", "").strip().upper() or "NONE"
        return SimulationStep(
            step_id, action, sender, receiver, message, delay_ms, priority, simulate_error
        )

    @staticmethod
    def _parse_int(value: str, field: str, line: int) -> int:
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(
                f"Dòng {line}, cột '{field}': phải là số nguyên, nhận được {value!r}."
            ) from error
