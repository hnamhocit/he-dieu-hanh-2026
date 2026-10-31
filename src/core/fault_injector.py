import random
import time
import os
import sys

class FaultInjector:
    def __init__(self, checksum_fail_rate=0.0, delay_range=(0.0, 0.0), crash_rate=0.0):
        """
        Khởi tạo cấu hình chèn lỗi.
        :param checksum_fail_rate: Tỉ lệ gây lỗi checksum (0.0 đến 1.0)
        :param delay_range: Khoảng thời gian trễ ngẫu nhiên (tuple: (min_seconds, max_seconds))
        :param crash_rate: Tỉ lệ giả lập crash tiến trình (0.0 đến 1.0)
        """
        self.checksum_fail_rate = checksum_fail_rate
        self.delay_range = delay_range
        self.crash_rate = crash_rate

    def inject_checksum(self, original_checksum):
        """Bơm checksum sai ngẫu nhiên."""
        if random.random() < self.checksum_fail_rate:
            print("[FAULT] 💥 Đang bơm checksum SAI...")
            return "ERR_CHECKSUM_FAILED"
        return original_checksum

    def inject_delay(self):
        """Giả lập trễ ngẫu nhiên để test Timeout."""
        min_delay, max_delay = self.delay_range
        if max_delay > min_delay:
            delay_time = random.uniform(min_delay, max_delay)
            if delay_time > 0:
                print(f"[FAULT] ⏳ Giả lập trễ {delay_time:.3f} giây...")
                time.sleep(delay_time)

    def simulate_crash(self, position_message=""):
        """Giả lập tiến trình bị chết đột ngột (Kill cứng)."""
        if random.random() < self.crash_rate:
            print(f"[FAULT] 💀 TIẾN TRÌNH BỊ ĐỨT ĐỘT NGỘT TẠI: {position_message}")
            sys.stdout.flush()
            os._exit(1) # Thoát ngay lập tức, không chạy các khối finally/cleanup
