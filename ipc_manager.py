import time
import threading
from typing import Optional

class MessagePacket:
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
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.queue = []
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)

    def enqueue(self, packet: MessagePacket, timeout: Optional[float] = None) -> bool:
        start_time = time.time()
        
        with self.not_full:
            while len(self.queue) >= self.capacity:
                if timeout == 0:
                    return False
                
                if timeout is not None:
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return False
                    self.not_full.wait(timeout=remaining)
                else:
                    self.not_full.wait()
            
            self.queue.append(packet)
            self.not_empty.notify()
            return True  # Quan trọng: Đảm bảo có dòng trả về True này!

    def dequeue(self, timeout: Optional[float] = None) -> Optional[MessagePacket]:
        start_time = time.time()
        
        with self.not_empty:
            while len(self.queue) == 0:
                if timeout == 0:
                    return None
                
                if timeout is not None:
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return None
                    self.not_empty.wait(timeout=remaining)
                else:
                    self.not_empty.wait()
            
            packet = self.queue.pop(0)
            self.not_full.notify()
            return packet