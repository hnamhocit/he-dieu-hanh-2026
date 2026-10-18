import time
import threading
from typing import Optional

class MessagePacket:
    """Định nghĩa cấu trúc khuôn mẫu cho một gói tin (MessagePacket)"""
    def __init__(self, packet_id: int, sender: str, receiver: str, message: str, delay_ms: int = 0, simulate_error: str = "NONE"):
        self.id = packet_id
        self.sender = sender
        self.receiver = receiver
        self.mechanism = "MESSAGE_QUEUE"
        self.message = message
        self.payload_size_bytes = len(message.encode('utf-8'))
        self.delay_ms = delay_ms
        self.simulate_error = simulate_error
        self.timestamp = time.time()


class MessageQueueCore:
    """Hiện thực lõi hàng đợi tin nhắn FIFO hỗ trợ an toàn luồng (Thread-safe)"""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.queue = []
        self.lock = threading.Lock()  

    def enqueue(self, packet: MessagePacket, timeout: Optional[float] = None) -> bool:
        """
        Đẩy gói tin vào hàng đợi (FIFO).
        - Trả về True nếu thêm thành công, False nếu hàng đợi đã đầy (Non-blocking/Timeout).
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                if len(self.queue) < self.capacity:
                    self.queue.append(packet)
                    return True
            if timeout == 0:
                return False
            if timeout is not None and (time.time() - start_time) >= timeout:
                return False
            time.sleep(0.01)

    def dequeue(self, timeout: Optional[float] = None) -> Optional[MessagePacket]:
        """
        Lấy gói tin ra khỏi hàng đợi theo cơ chế FIFO.
        - Trả về MessagePacket nếu lấy thành công, None nếu hàng đợi rỗng (Timeout).
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                if len(self.queue) > 0:
                    return self.queue.pop(0)  
            if timeout == 0:
                return None
            if timeout is not None and (time.time() - start_time) >= timeout:
                return None
            time.sleep(0.01)
