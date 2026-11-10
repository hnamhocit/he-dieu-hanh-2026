"""
Unit Test: test_message_queue.py
Kiểm thử toàn diện module Message Queue theo yêu cầu Jira HDH-14, 15, 27, 28, 29, 88, 95.
Đảm bảo kiểm tra đầy đủ: FIFO, Priority, Tie-breaking, Blocking, Non-blocking, Timeout, và get_state().
"""

import threading
import time
import unittest

from src.core.ipc_interface import IPCStatus
from src.core.message_queue import MessagePacket, MessageQueue


class TestMessageQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.capacity = 3
        self.mq = MessageQueue(capacity=self.capacity, is_priority=False)

    def test_init_validation(self) -> None:
        """Kiểm tra khởi tạo hợp lệ và ngoại lệ khi capacity <= 0."""
        self.assertEqual(self.mq.capacity, 3)
        self.assertEqual(self.mq.count, 0)
        self.assertTrue(self.mq.is_empty)
        self.assertFalse(self.mq.is_full)
        with self.assertRaises(ValueError):
            MessageQueue(capacity=0)
        with self.assertRaises(ValueError):
            MessageQueue(capacity=-2)

    def test_fifo_produce_consume(self) -> None:
        """Kiểm tra sản xuất và tiêu thụ theo chuẩn FIFO."""
        pkt1 = MessagePacket(id=1, sender="P1", receiver="C1", message="Msg 1")
        pkt2 = MessagePacket(id=2, sender="P1", receiver="C1", message="Msg 2")

        res1 = self.mq.produce(pkt1)
        self.assertTrue(res1.success)
        self.assertEqual(res1.status, IPCStatus.SUCCESS.value)

        res2 = self.mq.produce(pkt2)
        self.assertTrue(res2.success)
        self.assertEqual(self.mq.count, 2)

        # Lấy ra phải theo đúng thứ tự 1 trước, 2 sau
        cons1 = self.mq.consume()
        self.assertTrue(cons1.success)
        self.assertEqual(cons1.data.id, 1)

        cons2 = self.mq.consume()
        self.assertTrue(cons2.success)
        self.assertEqual(cons2.data.id, 2)
        self.assertTrue(self.mq.is_empty)

    def test_priority_queue_ordering(self) -> None:
        """Kiểm tra chế độ Priority Queue: gói tin ưu tiên cao hơn phải được lấy ra trước."""
        priority_mq = MessageQueue(capacity=4, is_priority=True)

        low_pkt = MessagePacket(id=1, sender="P1", receiver="C1", message="Low", priority=0)
        high_pkt = MessagePacket(id=2, sender="P1", receiver="C1", message="High", priority=5)
        med_pkt = MessagePacket(id=3, sender="P1", receiver="C1", message="Med", priority=2)

        priority_mq.produce(low_pkt)
        priority_mq.produce(high_pkt)
        priority_mq.produce(med_pkt)

        # Thứ tự lấy ra phải là: High (5) -> Med (2) -> Low (0)
        first = priority_mq.consume().data
        second = priority_mq.consume().data
        third = priority_mq.consume().data

        self.assertEqual(first.id, 2)
        self.assertEqual(second.id, 3)
        self.assertEqual(third.id, 1)

    def test_buffer_full_non_blocking(self) -> None:
        """Kiểm tra khi hàng đợi đầy ở chế độ non-blocking trả về cờ BLOCKED."""
        for i in range(self.capacity):
            res = self.mq.produce(MessagePacket(id=i + 1, sender="P", receiver="C", message=f"M{i}"))
            self.assertTrue(res.success)

        self.assertTrue(self.mq.is_full)

        # Lần gửi thứ 4 phải bị BLOCKED (không bị crash hay treo)
        overflow_pkt = MessagePacket(id=99, sender="P", receiver="C", message="Overflow")
        res_blocked = self.mq.produce(overflow_pkt, timeout=0.0)

        self.assertFalse(res_blocked.success)
        self.assertEqual(res_blocked.status, IPCStatus.BLOCKED.value)
        self.assertTrue(res_blocked.is_blocked)

    def test_buffer_empty_non_blocking(self) -> None:
        """Kiểm tra khi hàng đợi rỗng ở chế độ non-blocking trả về cờ BLOCKED."""
        self.assertTrue(self.mq.is_empty)
        res = self.mq.consume(timeout=0.0)

        self.assertFalse(res.success)
        self.assertEqual(res.status, IPCStatus.BLOCKED.value)
        self.assertTrue(res.is_blocked)

    def test_blocking_produce_with_condition_variable(self) -> None:
        """Kiểm tra Producer bị chặn khi đầy và được đánh thức khi Consumer lấy tin."""
        # Làm đầy hàng đợi
        for i in range(self.capacity):
            self.mq.produce(f"Msg {i}")

        # Luồng Consumer trễ lấy tin sau 0.3s
        def delayed_consume():
            time.sleep(0.3)
            self.mq.consume()

        th = threading.Thread(target=delayed_consume)
        th.start()

        start = time.time()
        res = self.mq.produce("Blocked Item", timeout=None)
        elapsed = time.time() - start

        th.join()
        self.assertTrue(res.success)
        self.assertGreaterEqual(elapsed, 0.25)

    def test_blocking_consume_with_condition_variable(self) -> None:
        """Kiểm tra Consumer bị chặn khi rỗng và được đánh thức khi Producer nạp tin."""
        def delayed_produce():
            time.sleep(0.3)
            self.mq.produce("Wakeup Message")

        th = threading.Thread(target=delayed_produce)
        th.start()

        start = time.time()
        res = self.mq.consume(timeout=None)
        elapsed = time.time() - start

        th.join()
        self.assertTrue(res.success)
        self.assertGreaterEqual(elapsed, 0.25)
        self.assertEqual(res.data.message, "Wakeup Message")

    def test_timeout_behavior(self) -> None:
        """Kiểm tra cơ chế timeout trả về TIMEOUT."""
        # Đầy buffer rồi thử produce với timeout nhỏ
        for i in range(self.capacity):
            self.mq.produce(f"Fill {i}")

        res = self.mq.produce("Timeout item", timeout=0.1)
        self.assertFalse(res.success)
        self.assertEqual(res.status, IPCStatus.TIMEOUT.value)

    def test_get_state_snapshot(self) -> None:
        """Kiểm tra snapshot get_state() phục vụ GUI rendering."""
        pkt = MessagePacket(id=10, sender="ProcA", receiver="ProcB", message="Hello GUI", priority=1)
        self.mq.produce(pkt)

        state = self.mq.get_state()
        self.assertEqual(state["mechanism"], "MESSAGE_QUEUE")
        self.assertEqual(state["capacity"], 3)
        self.assertEqual(state["count"], 1)
        self.assertEqual(state["empty"], 2)
        self.assertEqual(state["full"], 1)
        self.assertIsNotNone(state["buffer"][0])
        self.assertIsNone(state["buffer"][1])
        self.assertIsNone(state["buffer"][2])

    def test_legacy_enqueue_dequeue(self) -> None:
        """Kiểm tra khả năng tương thích ngược của enqueue() và dequeue()."""
        pkt = MessagePacket(id=100, sender="Legacy", receiver="App", message="Test")
        self.assertTrue(self.mq.enqueue(pkt, timeout=0))
        item = self.mq.dequeue(timeout=0)
        self.assertIsNotNone(item)
        self.assertEqual(item.id, 100)

    def test_reset(self) -> None:
        """Kiểm tra hàm reset làm sạch hàng đợi."""
        self.mq.produce("Item 1")
        self.mq.produce("Item 2")
        self.mq.reset()
        self.assertTrue(self.mq.is_empty)
        self.assertEqual(self.mq.count, 0)


def _produce_named(mq: MessageQueue, name: str, priority: int = 0) -> None:
    """Gửi một gói tin có nội dung `name` vào hàng đợi (non-blocking) và kiểm tra thành công."""
    result = mq.produce({"message": name, "priority": priority}, process_id="P", timeout=0.0)
    assert result.status == IPCStatus.SUCCESS.value


def _consume_all_names(mq: MessageQueue) -> list[str]:
    """Lấy hết gói tin ra (non-blocking) và trả về danh sách nội dung theo thứ tự lấy ra."""
    names: list[str] = []
    while True:
        result = mq.consume(process_id="C", timeout=0.0)
        if not result.success:
            return names
        names.append(result.data.message)


class TestTieBreaking(unittest.TestCase):
    """HDH-88: luật phân xử hòa khi nhiều gói tin có cùng mức Priority."""

    def test_same_priority_is_fifo(self) -> None:
        """Cùng priority thì gói tin vào hàng đợi trước phải được lấy ra trước."""
        mq = MessageQueue(capacity=10, is_priority=True)
        for name, priority in (("A", 1), ("B", 5), ("C", 5), ("D", 5), ("E", 1)):
            _produce_named(mq, name, priority)
        self.assertEqual(_consume_all_names(mq), ["B", "C", "D", "A", "E"])

    def test_higher_priority_jumps_ahead(self) -> None:
        """Gói tin priority cao hơn vào sau vẫn phải được lấy ra trước."""
        mq = MessageQueue(capacity=10, is_priority=True)
        _produce_named(mq, "low", 0)
        _produce_named(mq, "high", 9)
        self.assertEqual(_consume_all_names(mq), ["high", "low"])

    def test_fifo_mode_ignores_priority(self) -> None:
        """Chế độ FIFO không xét priority."""
        mq = MessageQueue(capacity=10, is_priority=False)
        _produce_named(mq, "A", 1)
        _produce_named(mq, "B", 9)
        _produce_named(mq, "C", 5)
        self.assertEqual(_consume_all_names(mq), ["A", "B", "C"])

    def test_sequence_increases_and_resets(self) -> None:
        """sequence tăng dần theo thứ tự vào hàng đợi và về 0 sau reset()."""
        mq = MessageQueue(capacity=10, is_priority=True)
        _produce_named(mq, "A")
        _produce_named(mq, "B")
        sequences = [item["sequence"] for item in mq.get_state()["items"]]
        self.assertEqual(sequences, [0, 1])
        mq.reset()
        _produce_named(mq, "C")
        self.assertEqual(mq.get_state()["items"][0]["sequence"], 0)


class TestBlockedState(unittest.TestCase):
    """HDH-88: trạng thái chặn và snapshot get_state() theo quy định nhóm."""

    def test_timeout_clears_blocked_process(self) -> None:
        """Sau khi TIMEOUT, tiến trình không còn nằm trong blocked_processes."""
        mq = MessageQueue(capacity=1)
        _produce_named(mq, "A")
        result = mq.produce("B", process_id="P2", timeout=0.05)
        self.assertEqual(result.status, IPCStatus.TIMEOUT.value)
        self.assertEqual(mq.get_state()["blocked_processes"], [])

    def test_get_state_has_required_keys(self) -> None:
        """get_state() có đủ các khóa bắt buộc và mutex = 1 khi không ai giữ khóa."""
        state = MessageQueue(capacity=3).get_state()
        for key in ("buffer", "in_ptr", "out_ptr", "mutex", "empty", "full", "blocked_processes"):
            self.assertIn(key, state)
        self.assertEqual(state["mutex"], 1)
        self.assertEqual((state["empty"], state["full"]), (3, 0))


class TestExceptionHandling(unittest.TestCase):
    """HDH-95: bắt lỗi Timeout, Queue Overflow/Underflow, đầu vào sai và tie-breaking."""

    def test_overflow_non_blocking_returns_blocked_immediately(self) -> None:
        """Queue Overflow ở chế độ non-blocking: trả về BLOCKED ngay, detail ghi rõ QUEUE_OVERFLOW."""
        mq = MessageQueue(capacity=1)
        _produce_named(mq, "A")
        start = time.time()
        result = mq.produce("B", timeout=0.0)
        self.assertLess(time.time() - start, 0.2)
        self.assertEqual(result.status, IPCStatus.BLOCKED.value)
        self.assertIn("QUEUE_OVERFLOW", result.detail)
        self.assertEqual(mq.count, 1)

    def test_underflow_non_blocking_returns_blocked_immediately(self) -> None:
        """Queue Underflow ở chế độ non-blocking: trả về BLOCKED ngay, detail ghi rõ QUEUE_UNDERFLOW."""
        mq = MessageQueue(capacity=2)
        start = time.time()
        result = mq.consume(timeout=0.0)
        self.assertLess(time.time() - start, 0.2)
        self.assertEqual(result.status, IPCStatus.BLOCKED.value)
        self.assertIn("QUEUE_UNDERFLOW", result.detail)

    def test_consume_timeout_on_empty_queue(self) -> None:
        """Consume có timeout trên hàng đợi rỗng trả về TIMEOUT và dọn trạng thái chặn."""
        mq = MessageQueue(capacity=2)
        start = time.time()
        result = mq.consume(process_id="C9", timeout=0.1)
        self.assertGreaterEqual(time.time() - start, 0.09)
        self.assertEqual(result.status, IPCStatus.TIMEOUT.value)
        self.assertEqual(mq.get_state()["blocked_processes"], [])

    def test_invalid_timeout_returns_error(self) -> None:
        """timeout âm / NaN / sai kiểu trả về ERROR thay vì ném ngoại lệ hoặc treo."""
        mq = MessageQueue(capacity=2)
        for bad in (-1, -0.5, float("nan"), "abc", True):
            with self.subTest(timeout=bad):
                self.assertEqual(mq.produce("X", timeout=bad).status, IPCStatus.ERROR.value)
                self.assertEqual(mq.consume(timeout=bad).status, IPCStatus.ERROR.value)
        self.assertTrue(mq.is_empty)

    def test_invalid_packet_returns_error(self) -> None:
        """Gói tin có priority/delay_ms sai kiểu hoặc dict lỗi trả về ERROR, hàng đợi không đổi."""
        mq = MessageQueue(capacity=3, is_priority=True)
        bad_items = (
            {"message": "x", "priority": "cao"},
            {"message": "x", "delay_ms": "abc"},
            {"message": "x", "delay_ms": -5},
            MessagePacket(id=1, sender="P", receiver="C", message="x", priority="high"),
        )
        for item in bad_items:
            with self.subTest(item=item):
                result = mq.produce(item, timeout=0.0)
                self.assertEqual(result.status, IPCStatus.ERROR.value)
                self.assertFalse(result.success)
        self.assertTrue(mq.is_empty)

    def test_payload_over_100_chars_rejected(self) -> None:
        """Guard: payload 101 ký tự bị từ chối, 100 ký tự được chấp nhận."""
        mq = MessageQueue(capacity=3)
        self.assertEqual(mq.produce("a" * 101, timeout=0.0).status, IPCStatus.ERROR.value)
        self.assertEqual(mq.produce("a" * 100, timeout=0.0).status, IPCStatus.SUCCESS.value)

    def test_error_does_not_break_later_operations(self) -> None:
        """Sau một lần lỗi, hàng đợi vẫn hoạt động bình thường."""
        mq = MessageQueue(capacity=2)
        mq.produce("x", timeout=-1)
        _produce_named(mq, "A")
        self.assertEqual(_consume_all_names(mq), ["A"])

    def test_simulate_error_kept_from_dict(self) -> None:
        """simulate_error trong dict không bị mất khi đóng gói thành MessagePacket."""
        mq = MessageQueue(capacity=2)
        result = mq.produce({"message": "m", "simulate_error": "checksum"}, timeout=0.0)
        self.assertEqual(result.data.simulate_error, "CHECKSUM")

    def test_resend_same_packet_object_keeps_order(self) -> None:
        """Gửi lại cùng một đối tượng gói tin khi nó còn trong hàng đợi không làm sai thứ tự tie-breaking."""
        mq = MessageQueue(capacity=5, is_priority=True)
        pkt = MessagePacket(id=1, sender="P", receiver="C", message="dup", priority=3)
        other = MessagePacket(id=2, sender="P", receiver="C", message="other", priority=3)
        mq.produce(pkt, timeout=0.0)
        mq.produce(other, timeout=0.0)
        mq.produce(pkt, timeout=0.0)
        self.assertEqual(_consume_all_names(mq), ["dup", "other", "dup"])

    def test_concurrent_same_priority_is_fifo_per_producer(self) -> None:
        """Nhiều Producer cùng priority chạy song song: sequence duy nhất, mỗi Producer giữ đúng thứ tự gửi."""
        # This test is kept for backward compatibility
        self._run_concurrent_test(capacity=200, num_workers=4, items_per_worker=25)

    def _run_concurrent_test(self, capacity: int, num_workers: int, items_per_worker: int) -> None:
        """Helper method to run concurrent stress test with configurable parameters."""
        mq = MessageQueue(capacity=200, is_priority=True)

        def worker(name: str) -> None:
            for i in range(25):
                mq.produce({"message": f"{name}{i}", "priority": 1}, process_id=name, timeout=None)

        threads = [threading.Thread(target=worker, args=(n,)) for n in "ABCD"]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        names = _consume_all_names(mq)
        self.assertEqual(len(names), 100)
        for n in "ABCD":
            own = [int(x[1:]) for x in names if x[0] == n]
            self.assertEqual(own, list(range(25)))

    def test_blocked_producer_woken_by_consumer_keeps_tie_order(self) -> None:
        """Producer bị chặn được đánh thức vẫn xếp sau các gói tin cùng priority đã có trong hàng đợi."""
        mq = MessageQueue(capacity=2, is_priority=True)
        _produce_named(mq, "A", 1)
        _produce_named(mq, "B", 1)

        def late_consume() -> None:
            time.sleep(0.2)
            mq.consume(process_id="C", timeout=0.0)

        th = threading.Thread(target=late_consume)
        th.start()
        result = mq.produce({"message": "C1", "priority": 1}, process_id="P3", timeout=2.0)
        th.join()
        self.assertTrue(result.success)
        self.assertEqual(_consume_all_names(mq), ["B", "C1"])


if __name__ == "__main__":
    unittest.main()
