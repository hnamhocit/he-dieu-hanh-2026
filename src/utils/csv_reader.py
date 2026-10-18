"""Đọc CSV kịch bản IPC và trả lỗi dữ liệu để bên gọi xử lý an toàn."""

from __future__ import annotations

import csv
from os import PathLike
from typing import Any


REQUIRED_COLUMNS = ("id", "action", "sender", "receiver")
NUMBER_COLUMNS = ("id", "delay_ms", "priority")


def _result(
    code: str, detail: str = "", data: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "success": code == "OK",
        "error_code": code,
        "detail": detail,
        "data": data if data is not None else [],
    }


def read_messages(path: str | PathLike[str]) -> dict[str, Any]:
    """Đọc toàn bộ file hoặc trả lỗi, không trả dữ liệu đã đọc dở.

    Kết quả gồm success, error_code, detail và data. Các trường id,
    delay_ms, priority được chuyển thành int. Hai trường số tùy chọn
    bị bỏ qua hoặc để trống có giá trị 0; message bị bỏ qua là chuỗi rỗng.
    Dòng trống được bỏ qua. Chỉ bắt đầu mô phỏng khi success là True.

    Hàm kiểm tra cấu trúc và định dạng số; các quy tắc nghiệp vụ như
    ID duy nhất, ID dương và action hợp lệ cần kiểm tra riêng.
    """
    messages: list[dict[str, Any]] = []

    try:
        with open(path, encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file, strict=True)
            headers = next(
                (cells for cells in reader if any(cell.strip() for cell in cells)),
                None,
            )
            if headers is None:
                return _result("EMPTY_FILE", "File không có nội dung.")

            if any(not name.strip() for name in headers):
                return _result("INVALID_CSV", "Tiêu đề có tên cột rỗng.")
            if len(headers) != len(set(headers)):
                return _result("INVALID_CSV", "Tiêu đề có tên cột trùng nhau.")

            missing = [name for name in REQUIRED_COLUMNS if name not in headers]
            if missing:
                return _result(
                    "MISSING_COLUMN", f"Thiếu cột: {', '.join(missing)}."
                )

            for cells in reader:
                if not any(cell.strip() for cell in cells):
                    continue

                line = reader.line_num
                if len(cells) < len(headers):
                    missing_cells = headers[len(cells):]
                    return _result(
                        "MISSING_COLUMN",
                        f"Dòng {line}: thiếu ô ở cột {', '.join(missing_cells)}.",
                    )
                if len(cells) > len(headers):
                    return _result(
                        "INVALID_CSV",
                        f"Dòng {line}: số ô nhiều hơn số cột trong tiêu đề.",
                    )

                row: dict[str, Any] = dict(zip(headers, cells))
                for column in NUMBER_COLUMNS:
                    value = row.get(column, "").strip()
                    if column != "id" and not value:
                        value = "0"
                    try:
                        row[column] = int(value)
                    except ValueError:
                        return _result(
                            "INVALID_NUMBER",
                            f"Dòng {line}, cột '{column}': "
                            f"{value!r} phải là số nguyên.",
                        )

                row.setdefault("message", "")
                messages.append(row)

    except (OSError, UnicodeError) as error:
        return _result("FILE_READ_ERROR", f"Không đọc được file: {error}")
    except csv.Error as error:
        return _result(
            "INVALID_CSV", f"CSV không hợp lệ gần dòng {reader.line_num}: {error}"
        )

    if not messages:
        return _result("EMPTY_FILE", "File không có dòng dữ liệu.")
    return _result("OK", data=messages)
