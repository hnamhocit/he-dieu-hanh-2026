"""
Module: test_shared_memory.py
Mô tả: Bộ kiểm thử đơn vị (Unit Tests) tự động cho module Shared Memory.
       Tương thích hoàn toàn với cả `pytest` lẫn `unittest`.
Task: HDH-24 - Test luồng lõi Shared Memory.
Python version: 3.10+
"""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
