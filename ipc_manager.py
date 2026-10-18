"""
Module: ipc_manager.py
Cung cấp khả năng tương thích ngược (Backward Compatibility) cho các script console cũ.
Khuyến nghị: Sử dụng trực tiếp 'from src.core.message_queue import MessageQueue, MessagePacket'.
"""

from src.core.message_queue import MessagePacket, MessageQueue, MessageQueueCore

__all__ = ["MessagePacket", "MessageQueue", "MessageQueueCore"]