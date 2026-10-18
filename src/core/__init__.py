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
