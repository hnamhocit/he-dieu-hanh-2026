import time
import queue
from collections import deque
from multiprocessing import Queue
import threading

class MetricsCalculator:
    def __init__(self, log_queue: queue.Queue, ipc_queue: Queue, interval: float = 1.0):
        """
        :param log_queue: Hàng đợi nhận log thô từ Trace Logger
        :param ipc_queue: Hàng đợi đẩy dữ liệu metrics đã tính toán sang IPC Manager (để lên GUI)
        :param interval: Chu kỳ tính toán và đẩy dữ liệu (giây), mặc định 1s
        """
        self.log_queue = log_queue
        self.ipc_queue = ipc_queue
        self.interval = interval
        
        self.running = False
        self.worker_thread = None

        # Lưu trữ thời điểm gửi của các packet để tính latency: {packet_id: send_timestamp}
        self.pending_packets = {}
        
        # Thống kê trong chu kỳ hiện tại
        self.current_period_sent = 0
        self.current_period_dropped = 0
        self.current_period_bytes = 0
        self.latencies = [] # Danh sách latency trong chu kỳ để tính trung bình/max

    def start(self):
        """Khởi động luồng xử lý metrics nền"""
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.worker_thread.start()
        print("[MetricsCalculator] Đã khởi động module trích xuất chỉ số.")

    def stop(self):
        """Dừng module"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join()
        print("[MetricsCalculator] Đã dừng module.")

    def _process_logs(self):
        last_time = time.time()
        
        while self.running:
            try:
                # Lấy log từ Trace Logger với timeout nhỏ để có thể ngắt luồng linh hoạt
                log_entry = self.log_queue.get(timeout=0.1)
                self._handle_log_event(log_entry)
            except queue.Empty:
                pass

            # Kiểm tra xem đã đến chu kỳ tính toán (ví dụ mỗi 1 giây) chưa
            now = time.time()
            if now - last_time >= self.interval:
                self._calculate_and_publish(now - last_time)
                last_time = now

    def _handle_log_event(self, log):
        """
        Xử lý từng dòng log hoặc event từ Trace Logger.
        Cấu trúc log mẫu giả định:
        {
            'timestamp': 1711234567.89,
            'packet_id': 'pkg_123',
            'status': 'SENT' | 'RECEIVED' | 'DROPPED',
            'size': 1024 (bytes)
        }
        """
        status = log.get('status')
        packet_id = log.get('packet_id')
        timestamp = log.get('timestamp', time.time())
        size = log.get('size', 0)

        if status == 'SENT':
            self.pending_packets[packet_id] = timestamp
            self.current_period_sent += 1
            self.current_period_bytes += size
            
        elif status == 'RECEIVED':
            if packet_id in self.pending_packets:
                send_time = self.pending_packets.pop(packet_id)
                latency = (timestamp - send_time) * 1000.0 # Đổi sang mili-giây (ms)
                self.latencies.append(latency)
                
        elif status == 'DROPPED':
            self.current_period_dropped += 1
            if packet_id in self.pending_packets:
                del self.pending_packets[packet_id]

    def _calculate_and_publish(self, elapsed_time):
        """Tính toán các chỉ số cuối chu kỳ và đẩy qua IPC Manager"""
        total_packets = self.current_period_sent + self.current_period_dropped
        
        # 1. Tỷ lệ Drop gói tin (%)
        drop_rate = (self.current_period_dropped / total_packets * 100.0) if total_packets > 0 else 0.0
        
        # 2. Throughput (Mbps hoặc Packets/s)
        throughput_pps = self.current_period_sent / elapsed_time
        throughput_bps = (self.current_period_bytes * 8) / elapsed_time / 1_000_000 # Mbps
        
        # 3. Latency tức thời (Trung bình, Min, Max trong chu kỳ)
        if self.latencies:
            avg_latency = sum(self.latencies) / len(self.latencies)
            max_latency = max(self.latencies)
            min_latency = min(self.latencies)
        else:
            avg_latency, max_latency, min_latency = 0.0, 0.0, 0.0

        # Đóng gói dữ liệu metrics chuẩn bị gửi lên GUI
        metrics_payload = {
            'timestamp': time.time(),
            'throughput_pps': round(throughput_pps, 2),
            'throughput_mbps': round(throughput_bps, 3),
            'drop_rate_pct': round(drop_rate, 2),
            'latency_avg_ms': round(avg_latency, 2),
            'latency_max_ms': round(max_latency, 2),
            'latency_min_ms': round(min_latency, 2),
            'total_sent': self.current_period_sent,
            'total_dropped': self.current_period_dropped
        }

        # Gửi sang IPC Manager để đẩy cho GUI
        try:
            self.ipc_queue.put_nowait(metrics_payload)
        except Exception as e:
            print(f"[MetricsCalculator Error] Không thể gửi dữ liệu qua IPC: {e}")

        # Reset bộ đếm cho chu kỳ tiếp theo
        self.current_period_sent = 0
        self.current_period_dropped = 0
        self.current_period_bytes = 0
        self.latencies.clear()