"""
Core IPC Module.
Cung cấp các cơ chế Inter-Process Communication chuẩn hóa kế thừa IIPCMechanism.
"""

from src.core.ipc_interface import IIPCMechanism, IPCResult, IPCStatus
from src.core.shared_memory import SharedMemory
from src.core.message_queue import MessageQueue, MessagePacket, MessageQueueCore
from src.core.fault_injector import FaultInjector 
__all__ = [
    "IIPCMechanism",
    "IPCResult",
    "IPCStatus",
    "SharedMemory",
    "MessageQueue",
    "MessagePacket",
    "MessageQueueCore",
]
import time
import os

TRACE_FILE_PATH = "data/output/trace_execution.csv"

def init_trace_logger():
    os.makedirs(os.path.dirname(TRACE_FILE_PATH), exist_ok=True)
    if not os.path.exists(TRACE_FILE_PATH):
        with open(TRACE_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("timestamp_ns,event_name,details\n")

def log_trace(event_name, details=""):
    timestamp = time.perf_counter_ns()
    safe_details = f'"{details}"' if ',' in str(details) else details
    with open(TRACE_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(f"{timestamp},{event_name},{safe_details}\n")

init_trace_logger()
