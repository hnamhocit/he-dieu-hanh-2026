"""
Core IPC Module.
Cung cấp các cơ chế Inter-Process Communication chuẩn hóa kế thừa IIPCMechanism.
"""

from src.core.ipc_interface import IIPCMechanism, IPCResult, IPCStatus
from src.core.shared_memory import SharedMemory
from src.core.message_queue import MessageQueue, MessagePacket, MessageQueueCore

__all__ = [
    "IIPCMechanism",
    "IPCResult",
    "IPCStatus",
    "SharedMemory",
    "MessageQueue",
    "MessagePacket",
    "MessageQueueCore",
]
import os
import csv
import time
from threading import Lock

# Đảm bảo thư mục đầu ra tồn tại
OUTPUT_DIR = "data/output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "trace_execution.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Khóa để ghi file đồng bộ nếu chạy đa luồng trong cùng 1 tiến trình
_log_lock = Lock()

# Khởi tạo tiêu đề file CSV nếu chưa có
if not os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_ns", "event_type", "details"])

def trace_log(event_type: str, details: str = ""):
    """Ghi vết vi sự kiện với timestamp nano giây chính xác cao"""
    timestamp = time.perf_counter_ns()
    with _log_lock:
        with open(OUTPUT_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, event_type, details])
