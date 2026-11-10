"""Benchmark Core IPC theo lô FIFO, độc lập với Qt và animation.

Một worker gửi đầy từng lô rồi nhận hết lô đó. Đây là phép đo mô phỏng
trong một luồng, không phải benchmark IPC giữa các OS process.
Trace mặc định của Core vẫn bật và được tính trong thời gian đo.
"""

from dataclasses import dataclass
from threading import Event
from time import perf_counter_ns

from src.core.message_queue import MessageQueue
from src.core.shared_memory import SharedMemory


class BenchmarkCancelled(Exception):
    """Người dùng dừng phép đo; không xuất kết quả của lần chạy dở."""


@dataclass(frozen=True)
class BenchmarkConfig:
    mechanisms: tuple[str, ...] = ("SHARED_MEMORY", "MESSAGE_QUEUE")
    message_count: int = 1000
    capacity: int = 16
    repeats: int = 3

    def validate(self):
        if not self.mechanisms or any(
            name not in {"SHARED_MEMORY", "MESSAGE_QUEUE"} for name in self.mechanisms
        ):
            raise ValueError("Cơ chế benchmark không hợp lệ.")
        for name, value, maximum in (
            ("Số thông điệp", self.message_count, 100000),
            ("Dung lượng buffer", self.capacity, 1024),
            ("Số lần chạy", self.repeats, 10),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} phải từ 1 đến {maximum}.")


@dataclass(frozen=True)
class BenchmarkResult:
    mechanism: str
    run: int
    message_count: int
    elapsed_seconds: float
    throughput: float
    latency_avg_ms: float
    latency_min_ms: float
    latency_max_ms: float


def run_benchmark(config, cancel=None, on_result=None):
    """Đo thông điệp nhận thành công/s và latency trước produce → sau consume.

    Kiểm tra ID/nội dung để không báo kết quả khi truyền sai hoặc mất dữ liệu.
    Callback được gọi trên luồng gọi hàm; GUI phải chuyển qua Qt signal.
    """
    config.validate()
    cancel = cancel if cancel is not None else Event()
    results = []

    def check_cancel():
        if cancel.is_set():
            raise BenchmarkCancelled()

    for run in range(1, config.repeats + 1):
        for name in config.mechanisms:
            check_cancel()
            core = SharedMemory(config.capacity) if name == "SHARED_MEMORY" else MessageQueue(config.capacity)
            latencies = []
            started = perf_counter_ns()
            for offset in range(0, config.message_count, config.capacity):
                pending = []
                for packet_id in range(offset, min(offset + config.capacity, config.message_count)):
                    check_cancel()
                    packet = {"id": packet_id, "sender": "BenchmarkProducer",
                              "receiver": "BenchmarkConsumer", "message": f"message-{packet_id}"}
                    sent = perf_counter_ns()
                    outcome = core.produce(packet)
                    if not outcome.success:
                        raise RuntimeError(f"{name}: gửi thất bại: {outcome.detail}")
                    pending.append((packet, sent))
                for packet, sent in pending:
                    check_cancel()
                    outcome = core.consume()
                    received = perf_counter_ns()
                    if not outcome.success:
                        raise RuntimeError(f"{name}: nhận thất bại: {outcome.detail}")
                    data = outcome.data
                    if hasattr(data, "to_dict"):
                        data = data.to_dict()
                    if not isinstance(data, dict) or any(data.get(k) != packet[k] for k in ("id", "message")):
                        raise RuntimeError(f"{name}: dữ liệu nhận không khớp thông điệp {packet['id']}.")
                    latencies.append((received - sent) / 1_000_000)
            elapsed = (perf_counter_ns() - started) / 1_000_000_000
            check_cancel()
            result = BenchmarkResult(
                name, run, len(latencies), elapsed, len(latencies) / elapsed,
                sum(latencies) / len(latencies), min(latencies), max(latencies),
            )
            results.append(result)
            if on_result is not None:
                on_result(result)
    return results
