"""
Core IPC Module.
Cung cấp các cơ chế Inter-Process Communication chuẩn hóa kế thừa IIPCMechanism.
"""

from __future__ import annotations

import os
import threading
import time

TRACE_FILE_PATH = "data/output/trace_execution.csv"
_trace_file_lock = threading.Lock()
_last_timestamp_ns = 0


def init_trace_logger() -> None:
    global _last_timestamp_ns
    try:
        os.makedirs(os.path.dirname(TRACE_FILE_PATH), exist_ok=True)
        if not os.path.exists(TRACE_FILE_PATH) or os.path.getsize(TRACE_FILE_PATH) == 0:
            with open(TRACE_FILE_PATH, "w", encoding="utf-8") as f:
                f.write("timestamp_ns,event_name,details\n")
        _last_timestamp_ns = 0
    except Exception:
        pass


def log_trace(event_name: str, details: str = "") -> None:
    global _last_timestamp_ns
    safe_details = f'"{details}"' if ',' in str(details) else str(details)
    try:
        with _trace_file_lock:
            current_ns = time.perf_counter_ns()
            if current_ns <= _last_timestamp_ns:
                current_ns = _last_timestamp_ns + 1
            _last_timestamp_ns = current_ns

            if not os.path.exists(TRACE_FILE_PATH) or os.path.getsize(TRACE_FILE_PATH) == 0:
                os.makedirs(os.path.dirname(TRACE_FILE_PATH), exist_ok=True)
                with open(TRACE_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write("timestamp_ns,event_name,details\n")
            with open(TRACE_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(f"{current_ns},{event_name},{safe_details}\n")
    except Exception:
        pass


# Khởi tạo file log trace khi nạp module
init_trace_logger()

from src.core.ipc_interface import IIPCMechanism, IPCResult, IPCStatus
from src.core.fault_injector import FaultInjector
from src.core.shared_memory import SharedMemory
from src.core.message_queue import MessagePacket, MessageQueue, MessageQueueCore

__all__ = [
    "IIPCMechanism",
    "IPCResult",
    "IPCStatus",
    "SharedMemory",
    "MessageQueue",
    "MessagePacket",
    "MessageQueueCore",
    "FaultInjector",
    "log_trace",
    "init_trace_logger",
    "TRACE_FILE_PATH",
]
