"""
Benchmark Stress Test cho Message Queue (HDH-112).

Dùng CÙNG bộ tải với benchmark Shared Memory (HDH-103):
    - Payload: 64 B, 1 KB, 64 KB, 1 MB, 10 MB.
    - Số gói tin N mỗi lượt: 10.000 đến 100.000 (chỉnh bằng --messages).
    - 5 Producer, 5 Consumer, hàng đợi Priority, capacity 20.

Các chỉ số đo (mỗi lượt đo cho ra một dòng):
    - throughput : thông lượng, gói tin/giây (msg/s).
    - latency    : độ trễ trung bình từ lúc gọi produce() đến lúc consume() trả về, mili giây.
    - Số lần chờ (blocking wait) trên not_full / not_empty và số context switch tự nguyện
      của tiến trình (chỉ Linux/macOS, Windows ghi N/A). Số lần wait() là số xấp xỉ cho
      context switch vì Python không đếm trực tiếp được.

Hai kịch bản:
    max_load : tải tối đa, Producer không nghỉ, không chèn lỗi, Consumer không trễ.
    full     : Consumer chậm (20 ms/gói) để hàng đợi chạm ngưỡng capacity, đo số lần chờ.

Trace log được TẮT khi đo (log_trace ghi file CSV sẽ làm lệch số đo).
Giới hạn 100 ký tự của tầng Guard được nâng tạm bằng MAX_PAYLOAD_CHARS chỉ trong lúc đo.

Chạy đo đầy đủ (ghi data/output/son_results.csv và son_blocking.csv):
    python -m tests.test_benchmark_message_queue --messages 10000 --runs 50
Chạy kiểm thử nhanh (unit test):
    python -m unittest tests.test_benchmark_message_queue -v
"""

import argparse
import concurrent.futures
import csv
import os
import statistics
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core import message_queue as mq_module
from src.core.message_queue import MessagePacket, MessageQueue

try:  # Chỉ có trên Linux/macOS
    import resource
except ImportError:  # Windows
    resource = None

PAYLOAD_SIZES = (64, 1024, 64 * 1024, 1024 * 1024, 10 * 1024 * 1024)
NUM_PRODUCERS = 5
NUM_CONSUMERS = 5
QUEUE_CAPACITY = 20
PRODUCE_TIMEOUT = 5.0
CONSUME_TIMEOUT = 0.05
SLOW_CONSUMER_DELAY = 0.02

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "output"))
RESULTS_CSV = os.path.join(OUTPUT_DIR, "son_results.csv")
BLOCKING_CSV = os.path.join(OUTPUT_DIR, "son_blocking.csv")


class WaitCounter:
    """Đếm số lần wait() trên một Condition, số lần được đánh thức và hết hạn."""

    def __init__(self, condition: threading.Condition) -> None:
        self.calls = 0
        self.woken = 0
        self.expired = 0
        self._lock = threading.Lock()
        self._original = condition.wait
        condition.wait = self._wrapped  # type: ignore[method-assign]

    def _wrapped(self, timeout=None):
        notified = self._original(timeout)
        with self._lock:
            self.calls += 1
            if notified:
                self.woken += 1
            else:
                self.expired += 1
        return notified


class BenchmarkEnvironment:
    """Tắt trace log và nâng giới hạn payload trong lúc đo, trả lại nguyên trạng khi xong."""

    def __enter__(self):
        self._old_trace = mq_module.log_trace
        self._old_limit = mq_module.MAX_PAYLOAD_CHARS
        mq_module.log_trace = lambda *args, **kwargs: None
        mq_module.MAX_PAYLOAD_CHARS = max(PAYLOAD_SIZES)
        return self

    def __exit__(self, *exc):
        mq_module.log_trace = self._old_trace
        mq_module.MAX_PAYLOAD_CHARS = self._old_limit
        return False


def _voluntary_switches():
    if resource is None:
        return None
    return resource.getrusage(resource.RUSAGE_SELF).ru_nvcsw


def run_once(payload_size: int, total_messages: int, scenario: str = "max_load",
             capacity: int = QUEUE_CAPACITY) -> dict:
    """Một lượt đo: gửi `total_messages` gói tin kích thước `payload_size` qua hàng đợi."""
    consumer_delay = SLOW_CONSUMER_DELAY if scenario == "full" else 0.0
    queue = MessageQueue(capacity=capacity, is_priority=True)
    full_waits = WaitCounter(queue._not_full)
    empty_waits = WaitCounter(queue._not_empty)

    payload = "x" * payload_size  # tạo một lần, không tính vào thời gian đo
    per_producer = total_messages // NUM_PRODUCERS
    total_sent = per_producer * NUM_PRODUCERS

    sent_at: dict[int, float] = {}
    latencies: list[float] = []
    stats = {"SUCCESS": 0, "BLOCKED": 0, "TIMEOUT": 0, "ERROR": 0}
    stats_lock = threading.Lock()
    producers_done = threading.Event()

    def producer(pid: int) -> None:
        for i in range(per_producer):
            msg_id = pid * 10_000_000 + i
            packet = MessagePacket(
                id=msg_id, sender=f"Producer_{pid}", receiver="Consumer_Worker",
                message=payload, priority=msg_id % 5,
            )
            sent_at[msg_id] = time.perf_counter()
            result = queue.produce(packet, process_id=packet.sender, timeout=PRODUCE_TIMEOUT)
            with stats_lock:
                stats[result.status] = stats.get(result.status, 0) + 1

    def consumer(cid: int) -> None:
        while True:
            result = queue.consume(process_id=f"Consumer_{cid}", timeout=CONSUME_TIMEOUT)
            if result.success:
                now = time.perf_counter()
                with stats_lock:
                    latencies.append(now - sent_at[result.data.id])
                if consumer_delay > 0:
                    time.sleep(consumer_delay)
            elif producers_done.is_set() and queue.is_empty:
                return

    switches_before = _voluntary_switches()
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_PRODUCERS + NUM_CONSUMERS) as ex:
        p_futs = [ex.submit(producer, i) for i in range(NUM_PRODUCERS)]
        c_futs = [ex.submit(consumer, i) for i in range(NUM_CONSUMERS)]
        concurrent.futures.wait(p_futs)
        producers_done.set()
        concurrent.futures.wait(c_futs)
    duration = time.perf_counter() - start
    switches_after = _voluntary_switches()

    received = len(latencies)
    return {
        "scenario": scenario,
        "payload_size": payload_size,
        "total_sent": total_sent,
        "received": received,
        "produce_success": stats["SUCCESS"],
        "produce_blocked": stats["BLOCKED"],
        "produce_timeout": stats["TIMEOUT"],
        "produce_error": stats["ERROR"],
        "duration_s": duration,
        "throughput": received / duration if duration > 0 else 0.0,
        "latency": statistics.mean(latencies) * 1000 if latencies else 0.0,
        "producer_waits": full_waits.calls,
        "consumer_waits": empty_waits.calls,
        "voluntary_switches": (
            None if switches_before is None or switches_after is None
            else switches_after - switches_before
        ),
        "queue_left": queue.count,
    }


def run_sweep(total_messages: int, runs: int, sizes=PAYLOAD_SIZES, scenario: str = "max_load"):
    """Đo `runs` lượt cho từng payload, trả về danh sách dòng kết quả."""
    rows = []
    with BenchmarkEnvironment():
        for size in sizes:
            for _ in range(runs):
                rows.append(run_once(size, total_messages, scenario))
    return rows


def save_results(rows: list[dict], path: str = RESULTS_CSV) -> None:
    """Ghi son_results.csv đúng định dạng plot_benchmarks.py: payload_size (byte), throughput (msg/s), latency (ms)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["payload_size", "throughput", "latency"])
        for r in rows:
            writer.writerow([r["payload_size"], f"{r['throughput']:.3f}", f"{r['latency']:.4f}"])


def save_blocking(rows: list[dict], path: str = BLOCKING_CSV) -> None:
    """Ghi file phụ: số lần chờ, context switch và kết quả khi hàng đợi chạm ngưỡng."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = ["scenario", "payload_size", "total_sent", "received", "produce_blocked",
            "produce_timeout", "produce_error", "duration_s", "throughput", "latency",
            "producer_waits", "consumer_waits", "voluntary_switches"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(keys)
        for r in rows:
            writer.writerow(["N/A" if r[k] is None else r[k] for k in keys])


def summarize(rows: list[dict]) -> None:
    print(f"{'kịch bản':>8} | {'payload':>9} | {'msg/s':>10} | {'trễ ms':>9} | "
          f"{'P chờ':>7} | {'C chờ':>7} | {'ctx sw':>8}")
    groups: dict = {}
    for r in rows:
        groups.setdefault((r["scenario"], r["payload_size"]), []).append(r)
    for (scenario, size), items in groups.items():
        sw = [i["voluntary_switches"] for i in items if i["voluntary_switches"] is not None]
        print(f"{scenario:>8} | {size:>9} | {statistics.mean(i['throughput'] for i in items):>10.1f} | "
              f"{statistics.mean(i['latency'] for i in items):>9.3f} | "
              f"{statistics.mean(i['producer_waits'] for i in items):>7.0f} | "
              f"{statistics.mean(i['consumer_waits'] for i in items):>7.0f} | "
              f"{(str(round(statistics.mean(sw))) if sw else 'N/A'):>8}")


class TestBenchmarkMessageQueue(unittest.TestCase):
    """Kiểm thử nhanh: tính đúng của benchmark với tải nhỏ."""

    def test_guard_limit_restored_after_benchmark(self) -> None:
        """Sau khi đo, giới hạn 100 ký tự và log_trace phải trở lại như cũ."""
        before_trace = mq_module.log_trace
        with BenchmarkEnvironment():
            self.assertGreater(mq_module.MAX_PAYLOAD_CHARS, 100)
        self.assertEqual(mq_module.MAX_PAYLOAD_CHARS, 100)
        self.assertIs(mq_module.log_trace, before_trace)

    def test_no_loss_all_payload_sizes(self) -> None:
        """Mọi payload (đến 1 MB) đi hết, không mất không trùng, hàng đợi rỗng."""
        with BenchmarkEnvironment():
            for size in (64, 1024, 64 * 1024, 1024 * 1024):
                with self.subTest(size=size):
                    r = run_once(size, total_messages=50)
                    self.assertEqual(r["produce_success"], r["total_sent"])
                    self.assertEqual(r["received"], r["total_sent"])
                    self.assertEqual(r["queue_left"], 0)
                    self.assertEqual(r["produce_error"], 0)
                    self.assertGreater(r["throughput"], 0)
                    self.assertGreater(r["latency"], 0)

    def test_full_queue_causes_producer_waits(self) -> None:
        """Consumer chậm thì hàng đợi chạm capacity: Producer phải chờ trên not_full."""
        with BenchmarkEnvironment():
            r = run_once(64, total_messages=100, scenario="full", capacity=5)
        self.assertGreater(r["producer_waits"], 0)
        self.assertEqual(r["received"], r["produce_success"])

    def test_csv_format_matches_plot_script(self) -> None:
        """son_results.csv có đúng 3 cột payload_size, throughput, latency."""
        import tempfile
        with BenchmarkEnvironment():
            rows = run_sweep(total_messages=20, runs=2, sizes=(64, 1024))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "son_results.csv")
            save_results(rows, path)
            with open(path, encoding="utf-8") as f:
                data = list(csv.DictReader(f))
        self.assertEqual(list(data[0].keys()), ["payload_size", "throughput", "latency"])
        self.assertEqual(len(data), 4)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Message Queue (HDH-112)")
    parser.add_argument("--messages", type=int, default=10000, help="N: số gói tin mỗi lượt (10.000-100.000)")
    parser.add_argument("--runs", type=int, default=50, help="số lượt đo mỗi payload")
    parser.add_argument("--big-messages", type=int, default=200,
                        help="N riêng cho payload >= 1 MB (tránh chạy quá lâu/tốn RAM)")
    args = parser.parse_args()

    rows = []
    with BenchmarkEnvironment():
        for size in PAYLOAD_SIZES:
            n = args.big_messages if size >= 1024 * 1024 else args.messages
            for _ in range(args.runs):
                rows.append(run_once(size, n, "max_load"))
            rows.append(run_once(size, min(n, 500), "full"))
    summarize(rows)
    save_results([r for r in rows if r["scenario"] == "max_load"])
    save_blocking(rows)
    print(f"Đã ghi {RESULTS_CSV} và {BLOCKING_CSV}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        main()
    else:
        unittest.main()