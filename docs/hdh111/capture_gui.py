"""Chụp GUI thật và vẽ chú thích bên cạnh, không thay đổi dữ liệu màn hình.

Chạy bằng Python đã cài requirements.txt:
  python docs/hdh111/capture_gui.py --source /path/to/source --output /tmp/hdh111

Source phải có HDH-110 (phiên bản gốc: b1ae0e6). Mặc định ghi ảnh, trace và
manifest vào /tmp/hdh111; chỉ ghi đè ảnh bàn giao khi chỉ định --output.
Đây là kiểm tra Qt offscreen, không thao tác hộp thoại hệ điều hành thật.
"""

import argparse
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
from time import monotonic

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hdh111-matplotlib")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument("--output", type=Path, default=Path("/tmp/hdh111"))
parser.add_argument("--source-ref", default="unspecified")
args = parser.parse_args()
source = args.source.resolve()
output = args.output.resolve()
inputs = Path(__file__).resolve().parent / "inputs"
output.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(source))
os.chdir(source)

from PyQt6.QtCore import QPoint, QRectF, Qt, QThreadPool
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.gui.main_window import MainWindow, UIState

app = QApplication.instance() or QApplication([])
app.setStyle("Fusion")
app.setFont(QFont("Segoe UI", 10))
window = MainWindow()
if not hasattr(window, "benchmark_tab"):
    raise RuntimeError("Source chưa có HDH-110; dùng commit b1ae0e6 hoặc bản đã tích hợp.")
window.resize(1280, 1080)
window.show()
observations = {}
images = []


def wait_until(predicate, timeout=15):
    deadline = monotonic() + timeout
    while not predicate() and monotonic() < deadline:
        QTest.qWait(10)
    if not predicate():
        raise AssertionError("Hết thời gian chờ GUI hoàn tất.")


def click(button):
    assert button.isEnabled(), button.text()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)


def load(path):
    # select_csv là điểm nhận đường dẫn sau hộp thoại Chọn file.
    window.select_csv(path)
    click(window.check_button)
    wait_until(lambda: window.state != UIState.LOADING)


def snapshot(filename, title, annotations):
    """Khung gốc được grab từ widget; đánh số và chú thích là lớp bổ sung."""
    app.processEvents()
    grabbed = window.grab()
    ratio = grabbed.devicePixelRatio()
    grabbed.setDevicePixelRatio(1)
    if ratio != 1:
        grabbed = grabbed.scaled(window.size())
    width, height = grabbed.width(), grabbed.height()
    image = QPixmap(width + 380, height + 130)
    image.fill(QColor("#eef2f7"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#0f172a"))
    painter.setFont(QFont("Arial", 21, QFont.Weight.Bold))
    painter.drawText(QRectF(24, 16, image.width() - 48, 36), title)
    painter.setFont(QFont("Arial", 11))
    painter.setPen(QColor("#64748b"))
    painter.drawText(24, 72, "HDH-111 · Ảnh GUI thực tế · Qt offscreen · Chú thích đánh số")
    painter.drawPixmap(20, 92, grabbed)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(QRectF(width + 38, 92, 320, height), 12, 12)
    for number, (widget, heading, description) in enumerate(annotations, 1):
        origin = widget.mapTo(window, QPoint(0, 0))
        rect = QRectF(origin.x() + 20, origin.y() + 92, widget.width(), widget.height())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#2563eb"), 2, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)
        x, y = rect.right() - 7, max(106, rect.top() - 7)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#2563eb"))
        painter.drawEllipse(QRectF(x - 14, y - 14, 28, 28))
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(QRectF(x - 14, y - 14, 28, 28), Qt.AlignmentFlag.AlignCenter, str(number))
        top = 116 + (number - 1) * 174
        painter.setPen(QColor("#2563eb"))
        painter.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        painter.drawText(QRectF(width + 58, top, 280, 44), Qt.TextFlag.TextWordWrap, f"{number:02d}  {heading}")
        painter.setPen(QColor("#475569"))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(QRectF(width + 58, top + 50, 278, 118), Qt.TextFlag.TextWordWrap, description)
    painter.end()
    assert image.save(str(output / filename))
    images.append(filename)


def trace_rows():
    return [[window.trace_table.item(row, col).text()
             for col in range(window.trace_table.columnCount())]
            for row in range(window.trace_table.rowCount())]


try:
    assert window.state == UIState.EMPTY and not window.start_button.isEnabled()
    observations["initial"] = {"state": window.state.value, "start_enabled": False}
    window.buffer_spin.setValue(2)
    load(Path("data/input/test_slots_edges.csv"))
    assert window.state == UIState.READY and len(window.messages) == 7
    observations["valid_csv"] = {"rows": len(window.messages), "start_enabled": window.start_button.isEnabled()}
    snapshot("01_csv_ready.png", "Hình 4.2-1 · Nạp và kiểm tra kịch bản CSV", [
        (window.file_path.parentWidget(), "Nạp kịch bản", "Chọn test_slots_edges.csv và nhấn Kiểm tra. File được xác thực trước khi cho chạy."),
        (window.file_feedback, "Kết quả xác thực", "CSV hợp lệ, 7 bước. Chỉ khi file hợp lệ thì nút Start mới được bật."),
        (window.mechanism_combo.parentWidget(), "Cấu hình mô phỏng", "Shared Memory, buffer 2 ô. Số Producer và Consumer được suy ra từ CSV."),
        (window.buffer_slots, "Vùng nhớ ban đầu", "Hai ô đều rỗng. Empty = 2, Full = 0; IN = OUT = 0."),
    ])

    steps = []

    def collect_shared(event):
        state = event["snapshot"]
        steps.append({"step": event["step"]["id"], "status": event["result"].status,
                      "buffer": state["buffer"], "in_ptr": state["in_ptr"],
                      "out_ptr": state["out_ptr"], "empty": state["empty"], "full": state["full"]})

    window.controller.step_completed.connect(collect_shared)
    window.controller.animation_ms = 180
    click(window.start_button)
    wait_until(lambda: window.buffer_slots.slot_state(0) == "WRITING")
    click(window.pause_button)
    assert window.state == UIState.PAUSED
    assert window.start_button.text() == "Tiếp tục"
    observations["pause"] = {"state": window.state.value, "slot_0": window.buffer_slots.slot_state(0),
                             "resume_button": window.start_button.text()}
    snapshot("02_pause_writing.png", "Hình 4.2-2 · Tạm dừng để quan sát thao tác ghi", [
        (window.buffer_slots, "Frame đang ghi", "Ô 0 hiện màu tím WRITING. Đây là frame được phát lại từ sự kiện Core."),
        (window.sync_state_label, "Biến đồng bộ", "Giá trị là snapshot tại frame. Animation không giữ mutex thật trong thời gian hiển thị."),
        (window.start_button, "Tiếp tục phiên", "Pause giữ frame hiện tại. Nhấn Tiếp tục để phát tiếp; không bắt đầu lại CSV."),
    ])
    window.controller.animation_ms = 0
    click(window.start_button)
    wait_until(lambda: window.state == UIState.READY)
    window.controller.step_completed.disconnect(collect_shared)
    rows = trace_rows()
    statuses = [row[6] for row in rows]
    assert statuses == ["SUCCESS", "SUCCESS", "BLOCKED", "SUCCESS", "SUCCESS", "BLOCKED", "SUCCESS"]
    assert [(s["in_ptr"], s["out_ptr"], s["empty"], s["full"]) for s in steps] == [
        (1, 0, 1, 1), (0, 0, 0, 2), (0, 0, 0, 2), (0, 1, 1, 1),
        (0, 0, 2, 0), (0, 0, 2, 0), (1, 0, 1, 1),
    ]
    assert [[item["message"] if item is not None else None for item in s["buffer"]] for s in steps] == [
        ["Hello", None], ["Hello", "World"], ["Hello", "World"], [None, "World"],
        [None, None], [None, None], ["Wrap around", None],
    ]
    state = window.controller.core.get_state()
    assert (state["count"], state["empty"], state["full"], state["in_ptr"], state["out_ptr"]) == (1, 1, 1, 1, 0)
    assert state["buffer"][0]["message"] == "Wrap around" and state["buffer"][1] is None
    assert window.export_trace(output / "shared_memory_trace.csv")
    with (output / "shared_memory_trace.csv").open(encoding="utf-8-sig", newline="") as stream:
        exported = list(csv.reader(stream))
    assert len(exported) == 8 and exported[1:] == rows
    observations["shared_memory"] = {"statuses": statuses, "count": state["count"], "empty": state["empty"],
                                     "full": state["full"], "in_ptr": state["in_ptr"], "out_ptr": state["out_ptr"],
                                     "exported_rows": len(exported) - 1, "export_matches_table": True,
                                     "steps": steps}
    snapshot("03_shared_memory_results.png", "Hình 4.2-3 · Đầy, rỗng và quay vòng buffer", [
        (window.buffer_slots, "Quay vòng về ô 0", "Sau bước 7, ô 0 chứa Wrap around; ô 1 rỗng. IN = 1 và OUT = 0."),
        (window.sync_state_label, "Đối chiếu trạng thái", "Empty = 1, Full = 1, tổng bằng capacity = 2. Buffer còn đúng một thông điệp."),
        (window.trace_table, "Đọc kết quả từng bước", "Bước 3 BLOCKED do đầy; bước 6 BLOCKED do rỗng. Các bước còn lại SUCCESS; không tự retry bước bị chặn."),
        (window.export_button, "Xuất bằng chứng", "Xuất Trace CSV lưu 7 dòng dữ liệu với UTF-8 BOM. Đã đối chiếu nội dung xuất với bảng GUI."),
    ])
    click(window.reset_button)
    assert window.trace_table.rowCount() == 0 and len(window.messages) == 7
    assert window.state == UIState.READY and not window.export_button.isEnabled()
    observations["reset"] = {"trace_rows": 0, "csv_rows_retained": 7, "state": window.state.value}

    load(Path("data/input/invalid_format.csv"))
    assert window.state == UIState.SELECTED and not window.start_button.isEnabled()
    assert "INVALID_DATA" in window.file_feedback.text() and window.messages == []
    observations["invalid_csv"] = {"feedback": window.file_feedback.text(), "start_enabled": False, "messages": 0}
    snapshot("04_invalid_csv.png", "Hình 4.2-4 · Từ chối dữ liệu đầu vào không hợp lệ", [
        (window.file_name_label.parentWidget(), "File không hợp lệ", "invalid_format.csv dùng header không khớp hợp đồng CSV hiện tại."),
        (window.file_feedback, "Thông báo có nguyên nhân", "GUI hiện INVALID_DATA và chi tiết thiếu cột. Không nạp dữ liệu dở vào mô phỏng."),
        (window.start_button, "Chặn chạy dữ liệu lỗi", "Start bị vô hiệu hóa. Người dùng vẫn có thể Chọn file khác rồi Kiểm tra lại."),
    ])

    load(inputs / "priority_demo.csv")
    assert window.state == UIState.READY
    window.mechanism_combo.setCurrentIndex(2)
    assert window.priority_checkbox.isEnabled()
    window.priority_checkbox.setChecked(True)
    window.buffer_spin.setValue(2)
    received_ids = []

    def collect(event):
        if event["step"]["action"] == "RECEIVE":
            packet = event["result"].data
            received_ids.append(packet.id)

    window.controller.step_completed.connect(collect)
    click(window.start_button)
    wait_until(lambda: window.state == UIState.READY)
    window.controller.step_completed.disconnect(collect)
    assert received_ids == [2, 1]
    assert all(row[6] == "SUCCESS" for row in trace_rows())
    assert window.export_trace(output / "message_queue_trace.csv")
    observations["priority_queue"] = {"received_packet_ids": received_ids, "statuses": [row[6] for row in trace_rows()]}
    snapshot("05_priority_queue.png", "Hình 4.2-5 · Kiểm tra Message Queue ưu tiên", [
        (window.priority_checkbox, "Bật hàng đợi ưu tiên", "Chọn Message Queue rồi bật Priority Queue. Buffer có 2 ô."),
        (window.sync_state_label, "Trạng thái kết thúc", "Queue: Priority. Cả hai thông điệp đã được nhận, Full = 0, Empty = 2."),
        (window.trace_table, "Đối chiếu thứ tự nhận", "Tin #2 có priority 5 được nhận trước tin #1 có priority 1 dù gửi sau. Cả 4 bước SUCCESS."),
    ])

    window.tabs.setCurrentIndex(1)
    tab = window.benchmark_tab
    tab.message_spin.setValue(1000)
    tab.capacity_spin.setValue(16)
    tab.repeats_spin.setValue(3)
    click(tab.run_button)
    assert not tab.run_button.isEnabled()
    wait_until(lambda: tab.worker is None, timeout=60)
    assert len(tab.results) == 6 and tab.progress.value() == tab.progress.maximum() == 6
    assert len(tab.throughput_axes.lines) == len(tab.latency_axes.lines) == 2
    from dataclasses import asdict
    benchmark = [asdict(result) for result in tab.results]
    with (output / "benchmark_results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=benchmark[0].keys())
        writer.writeheader()
        writer.writerows(benchmark)
    observations["benchmark"] = {"configuration": {"message_count": 1000, "capacity": 16, "repeats": 3},
                                 "completed_runs": len(benchmark), "results": benchmark,
                                 "throughput_series": 2, "latency_series": 2}
    snapshot("06_benchmark.png", "Hình 4.2-6 · Đo và đọc kết quả benchmark", [
        (tab.mechanism_combo.parentWidget(), "Cấu hình phép đo", "So sánh cả hai cơ chế: 1.000 tin/lần, buffer 16 ô, lặp 3 lần. Không cần CSV."),
        (tab.metric_labels[0].parentWidget(), "Thông lượng", "Số tin nhận thành công mỗi giây (msg/s). Thẻ thể hiện lần đo mới nhất, kèm cơ chế và số lần chạy."),
        (tab.metric_labels[1].parentWidget(), "Độ trễ", "Thời gian từ trước gửi đến sau nhận (ms), bao gồm chờ buffer. Không so trực tiếp với latency từng thao tác của tab mô phỏng."),
        (tab.canvas, "Hai biểu đồ", "Xanh dương: Shared Memory; xanh ngọc: Message Queue. Mỗi điểm ứng với một lần chạy."),
        (tab.table, "Bảng kết quả", "6 lần đo hoàn tất. Có số tin, thời gian, throughput và latency trung bình/min/max; số đo phụ thuộc môi trường."),
    ])
finally:
    window.close()
    QThreadPool.globalInstance().waitForDone(5000)
    app.processEvents()

manifest = {
    "source_ref": args.source_ref,
    "verification_date": "2026-11-07",
    "timezone": "Asia/Ho_Chi_Minh",
    "environment": {"os": platform.system(), "os_version": platform.mac_ver()[0] if sys.platform == "darwin" else platform.release(),
                    "architecture": platform.machine(), "python": platform.python_version(),
                    "PyQt6": importlib.metadata.version("PyQt6"), "matplotlib": importlib.metadata.version("matplotlib"),
                    "qt_platform": os.environ["QT_QPA_PLATFORM"], "window_size": "1280x1080"},
    "method": "Qt offscreen, QTest button clicks; file paths supplied at dialog return boundary; no mock Core results",
    "images": images,
    "observations": observations,
}
(output / "observations.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Verified {len(observations)} scenarios; wrote {len(images)} annotated screenshots to {output}")
