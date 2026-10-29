"""
Module: test_shared_memory.py
Mô tả: Bộ kiểm thử đơn vị (Unit Tests) tự động cho module Shared Memory.
       Tương thích hoàn toàn với cả `pytest` lẫn `unittest`.
Task: HDH-24 - Test luồng lõi Shared Memory.
Python version: 3.10+
"""

from __future__ import annotations

import threading
import time
import unittest
from src.core.shared_memory import SharedMemory
from src.core.ipc_interface import IPCStatus


class TestSharedMemory(unittest.TestCase):
    """Bộ test case kiểm chứng logic đồng bộ, biên và trạng thái của SharedMemory."""

    def setUp(self) -> None:
        self.capacity = 3
        self.shm = SharedMemory(capacity=self.capacity)

    def test_init_validation(self) -> None:
        """Kiểm tra khởi tạo hợp lệ và ngoại lệ khi capacity <= 0."""
        self.assertEqual(self.shm.capacity, 3)
        self.assertEqual(self.shm.count, 0)
        self.assertTrue(self.shm.is_empty)
        self.assertFalse(self.shm.is_full)

        with self.assertRaises(ValueError):
            SharedMemory(capacity=0)

        with self.assertRaises(ValueError):
            SharedMemory(capacity=-5)

    def test_produce_consume_single_item(self) -> None:
        """Kiểm tra sản xuất và tiêu thụ 1 phần tử cơ bản."""
        res_prod = self.shm.produce("Item_1", process_id="P1")
        self.assertTrue(res_prod.success)
        self.assertEqual(res_prod.status, IPCStatus.SUCCESS.value)
        self.assertEqual(self.shm.count, 1)

        state = self.shm.get_state()
        self.assertEqual(state["buffer"][0], "Item_1")
        self.assertEqual(state["in_ptr"], 1)
        self.assertEqual(state["out_ptr"], 0)
        self.assertEqual(state["empty"], 2)
        self.assertEqual(state["full"], 1)

        res_cons = self.shm.consume(process_id="C1")
        self.assertTrue(res_cons.success)
        self.assertEqual(res_cons.data, "Item_1")
        self.assertEqual(self.shm.count, 0)

        state_after = self.shm.get_state()
        self.assertIsNone(state_after["buffer"][0])  # Slot được xóa sạch về None
        self.assertEqual(state_after["out_ptr"], 1)
        self.assertEqual(state_after["empty"], 3)
        self.assertEqual(state_after["full"], 0)

    def test_buffer_full_non_blocking(self) -> None:
        """Kiểm tra tràn bộ đệm (Buffer Full) không làm treo luồng và trả về cờ BLOCKED."""
        # Ghi đầy bộ đệm (capacity = 3)
        self.shm.produce("A", process_id="P1")
        self.shm.produce("B", process_id="P1")
        self.shm.produce("C", process_id="P1")
        self.assertTrue(self.shm.is_full)

        # Thử ghi phần tử thứ 4 với timeout=0.0 (Non-blocking)
        res_overflow = self.shm.produce("D", process_id="P2", timeout=0.0)
        self.assertFalse(res_overflow.success)
        self.assertEqual(res_overflow.status, IPCStatus.BLOCKED.value)
        self.assertTrue(res_overflow.is_blocked)

        state = self.shm.get_state()
        self.assertIn("P2", state["blocked_processes"])
        self.assertEqual(state["empty"], 0)
        self.assertEqual(state["full"], 3)

    def test_buffer_empty_non_blocking(self) -> None:
        """Kiểm tra đọc từ bộ đệm rỗng (Buffer Empty) trả về cờ BLOCKED."""
        self.assertTrue(self.shm.is_empty)

        res_underflow = self.shm.consume(process_id="C1", timeout=0.0)
        self.assertFalse(res_underflow.success)
        self.assertEqual(res_underflow.status, IPCStatus.BLOCKED.value)
        self.assertTrue(res_underflow.is_blocked)

        state = self.shm.get_state()
        self.assertIn("C1", state["blocked_processes"])
        self.assertEqual(state["empty"], 3)
        self.assertEqual(state["full"], 0)

    def test_circular_wrap_around(self) -> None:
        """Kiểm tra cơ chế con trỏ mảng vòng (Modulo Wrap-around)."""
        # Ghi 3 phần tử (đầy slot 0, 1, 2)
        for i in range(3):
            self.shm.produce(f"Val_{i}")
        self.assertEqual(self.shm.in_ptr, 0)  # Wrap về 0

        # Đọc 2 phần tử (giải phóng slot 0, 1)
        self.assertEqual(self.shm.consume().data, "Val_0")
        self.assertEqual(self.shm.consume().data, "Val_1")
        self.assertEqual(self.shm.out_ptr, 2)

        # Ghi tiếp 2 phần tử mới (ghi vào slot 0, 1)
        self.shm.produce("Val_3")
        self.shm.produce("Val_4")
        self.assertEqual(self.shm.in_ptr, 2)

        # Trạng thái buffer: slot 0='Val_3', slot 1='Val_4', slot 2='Val_2'
        state = self.shm.get_state()
        self.assertEqual(state["buffer"], ["Val_3", "Val_4", "Val_2"])

    def test_reset_functionality(self) -> None:
        """Kiểm tra khôi phục trạng thái ban đầu."""
        self.shm.produce("Data")
        self.shm.reset()

        state = self.shm.get_state()
        self.assertEqual(state["buffer"], [None, None, None])
        self.assertEqual(state["count"], 0)
        self.assertEqual(state["in_ptr"], 0)
        self.assertEqual(state["out_ptr"], 0)
        self.assertEqual(state["mutex"], 1)
        self.assertEqual(state["empty"], 3)
        self.assertEqual(state["full"], 0)
        self.assertEqual(state["blocked_processes"], [])

    def test_events_capture_actual_locked_write_and_read_snapshots(self):
        written = []
        self.shm.produce({"id": 1, "message": "Hello"}, "P1", events=written)
        self.assertEqual([event["phase"] for event in written], ["LOCKED", "WRITING", "WRITTEN"])
        self.assertIsNone(written[0]["snapshot"]["buffer"][0])
        self.assertIsNone(written[1]["snapshot"]["buffer"][0])
        self.assertEqual(written[2]["snapshot"]["buffer"][0]["id"], 1)
        for event in written:
            self.assertEqual(event["snapshot"]["mutex"], 0)
            self.assertEqual(event["snapshot"]["mutex_holder"], "P1")
            self.assertEqual(event["slot_index"], 0)
        read = []
        self.shm.consume("C1", events=read)
        self.assertEqual([event["phase"] for event in read], ["LOCKED", "READING"])
        self.assertEqual(read[-1]["snapshot"]["buffer"][0]["id"], 1)
        self.assertIsNone(self.shm.get_state()["buffer"][0])
        self.assertEqual(self.shm.get_state()["mutex"], 1)
        # Các snapshot lịch sử không bị xóa khi Core thay đổi buffer.
        self.assertEqual(written[2]["snapshot"]["count"], 1)

    def test_blocked_operation_has_no_locked_animation(self):
        events = []
        self.assertTrue(self.shm.consume(events=events).is_blocked)
        self.assertEqual(events, [])

    def test_nonblocking_mutex_contention_restores_semaphore(self):
        self.shm._mutex.acquire()
        try:
            self.assertTrue(self.shm.produce("A", timeout=0.0).is_blocked)
        finally:
            self.shm._mutex.release()
        self.assertTrue(self.shm.produce("A"))
        self.shm._mutex.acquire()
        try:
            self.assertTrue(self.shm.consume(timeout=0.0).is_blocked)
        finally:
            self.shm._mutex.release()
        self.assertEqual(self.shm.consume().data, "A")

    def test_system_invariants_verification(self) -> None:
        """Kiểm chứng tính bất biến toán học của SharedMemory (HDH-86)."""
        ok, msg = self.shm.verify_invariants()
        self.assertTrue(ok, msg)

        self.shm.produce("Val_1")
        self.shm.produce("Val_2")
        ok, msg = self.shm.verify_invariants()
        self.assertTrue(ok, msg)

        self.shm.consume()
        ok, msg = self.shm.verify_invariants()
        self.assertTrue(ok, msg)

    def test_timeout_blocking_produce_and_consume(self) -> None:
        """Kiểm tra cơ chế timeout khi buffer đầy hoặc rỗng."""
        # Test consume timeout trên buffer rỗng
        res_cons = self.shm.consume("C1", timeout=0.05)
        self.assertFalse(res_cons.success)
        self.assertEqual(res_cons.status, IPCStatus.BLOCKED.value)

        # Lắp đầy buffer
        for i in range(self.capacity):
            self.shm.produce(f"Data_{i}")

        # Test produce timeout trên buffer đầy
        res_prod = self.shm.produce("Data_Overflow", "P1", timeout=0.05)
        self.assertFalse(res_prod.success)
        self.assertEqual(res_prod.status, IPCStatus.BLOCKED.value)

    def test_fault_injection_delay_and_checksum(self) -> None:
        """Kiểm tra xử lý mô phỏng lỗi DELAY và CHECKSUM mà không làm crash core."""
        # 1. DELAY
        item_delay = {"id": 1, "simulate_error": "DELAY", "delay_ms": 10, "message": "DelayTest"}
        res = self.shm.produce(item_delay, "P_Delay")
        self.assertTrue(res.success)
        self.assertEqual(self.shm.count, 1)

        # 2. CHECKSUM
        item_chk = {"id": 2, "simulate_error": "CHECKSUM", "message": "Original"}
        res2 = self.shm.produce(item_chk, "P_Chk")
        self.assertTrue(res2.success)

        # Consume ra và kiểm tra
        consumed_1 = self.shm.consume("C1").data
        self.assertEqual(consumed_1["id"], 1)

        consumed_2 = self.shm.consume("C1").data
        self.assertEqual(consumed_2["id"], 2)
        self.assertEqual(consumed_2.get("checksum"), "ERR_CHECKSUM_FAILED")

    def test_concurrent_multithreaded_producer_consumer(self) -> None:
        """Kiểm tra an toàn đa luồng tải cao không bị Race Condition hay Deadlock (HDH-86)."""
        import concurrent.futures
        shm = SharedMemory(capacity=5)
        num_items_per_worker = 30
        num_workers = 3
        total_items = num_items_per_worker * num_workers
        consumed_items = []
        lock_consumed = threading.Lock()

        def producer_worker(p_id: int):
            for i in range(num_items_per_worker):
                item = f"P{p_id}_{i}"
                while True:
                    res = shm.produce(item, process_id=f"P_{p_id}", timeout=0.01)
                    if res.success:
                        break
                    time.sleep(0.001)

        def consumer_worker(c_id: int):
            for _ in range(num_items_per_worker):
                while True:
                    res = shm.consume(process_id=f"C_{c_id}", timeout=0.01)
                    if res.success:
                        with lock_consumed:
                            consumed_items.append(res.data)
                        break
                    time.sleep(0.001)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers * 2) as pool:
            p_futs = [pool.submit(producer_worker, i) for i in range(num_workers)]
            c_futs = [pool.submit(consumer_worker, i) for i in range(num_workers)]
            concurrent.futures.wait(p_futs + c_futs)

        self.assertEqual(len(consumed_items), total_items)
        ok, msg = shm.verify_invariants()
        self.assertTrue(ok, msg)
        self.assertEqual(shm.count, 0)
        self.assertTrue(shm.is_empty)


if __name__ == "__main__":
    unittest.main()
