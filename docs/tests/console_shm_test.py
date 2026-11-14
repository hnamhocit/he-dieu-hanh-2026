"""
Script: console_shm_test.py
Mô tả: Giả lập môi trường đa luồng (Multi-threading) gồm 3 Producers và 2 Consumers
       chia sẻ cùng một vùng nhớ đệm Bounded Buffer (Shared Memory).
       In Trace Log chi tiết từng bước theo thời gian thực để chứng minh:
       1. Không xảy ra Race Condition (Không mất dữ liệu, không ghi đè, không đọc trùng).
       2. Không xảy ra Deadlock (Các tiến trình giải phóng khóa và báo hiệu Semaphore chuẩn xác).
       3. Xử lý chuẩn xác trạng thái BLOCKED khi Buffer Đầy hoặc Buffer Rỗng.
Task: HDH-24 - Test luồng lõi Shared Memory.
Python version: 3.10+
"""

from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime
from typing import Any

# Đảm bảo đường dẫn import hoạt động từ thư mục gốc của dự án
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.shared_memory import SharedMemory


class TraceLogger:
    """Bộ ghi log Trace dạng bảng chuẩn hóa, bảo vệ thread-safe khi in ra terminal."""

    def __init__(self) -> None:
        self._print_lock = threading.Lock()
        self._step = 0

    def print_header(self) -> None:
        header = (
            f"{'STEP':<6} | {'TIME':<12} | {'PROCESS':<10} | {'ACTION':<10} | "
            f"{'STATUS':<9} | {'BUFFER STATE':<22} | {'(M, E, F)':<11} | {'DETAIL'}"
        )
        separator = "-" * 115
        with self._print_lock:
            print("\n" + "=" * 115)
            print("                HỆ THỐNG TRACE LOG - MÔ PHỎNG IPC SHARED MEMORY (BOUNDED BUFFER)")
            print("=" * 115)
            print(header)
            print(separator)

    def log(
        self,
        process_id: str,
        action: str,
        status: str,
        state: dict[str, Any],
        detail: str,
    ) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        buf_str = str([item if item is not None else "_" for item in state["buffer"]])
        sem_str = f"({state['mutex']}, {state['empty']}, {state['full']})"

        with self._print_lock:
            self._step += 1
            row = (
                f"{self._step:<6} | {timestamp:<12} | {process_id:<10} | {action:<10} | "
                f"{status:<9} | {buf_str:<22} | {sem_str:<11} | {detail}"
            )
            print(row)


def run_simulation(
    capacity: int = 4,
    items_per_producer: int = 4,
    num_producers: int = 3,
    num_consumers: int = 2,
) -> tuple[bool, dict[str, Any]]:
    """
    Thực thi kịch bản giả lập đồng thời 3 Producers và 2 Consumers.

    Returns:
        tuple[bool, dict]: (Thành công hay không, Báo cáo đối soát Oracle).
    """
    shm = SharedMemory(capacity=capacity)
    logger = TraceLogger()
    logger.print_header()

    total_expected_items = num_producers * items_per_producer
    produced_items: list[str] = []
    consumed_items: list[str] = []
    produced_lock = threading.Lock()
    consumed_lock = threading.Lock()

    # Cờ báo hiệu các producer đã hoàn tất toàn bộ công việc
    all_producers_done = threading.Event()
    active_producers = num_producers
    active_producers_lock = threading.Lock()

    # -------------------------------------------------------------------------
    # LUỒNG PRODUCER
    # -------------------------------------------------------------------------
    def producer_worker(producer_id: str) -> None:
        nonlocal active_producers

        for i in range(1, items_per_producer + 1):
            item = f"{producer_id}-M{i}"

            # Thử ghi dữ liệu vào buffer bằng cơ chế non-blocking (timeout=0.0)
            while True:
                result = shm.produce(item, process_id=producer_id, timeout=0.0)
                state = shm.get_state()

                if result.status == "SUCCESS":
                    with produced_lock:
                        produced_items.append(item)
                    logger.log(producer_id, "PRODUCE", "SUCCESS", state, result.detail)
                    time.sleep(0.03)  # Thời gian tạo dữ liệu kế tiếp
                    break
                else:
                    # Rơi vào trạng thái BLOCKED do buffer đầy (Semaphore empty == 0)
                    logger.log(
                        producer_id,
                        "PRODUCE",
                        "BLOCKED",
                        state,
                        f"Buffer ĐẦY! [{producer_id}] bị BLOCKED tại Semaphore empty, đợi Consumer giải phóng ô nhớ...",
                    )
                    time.sleep(0.06)

        with active_producers_lock:
            active_producers -= 1
            if active_producers == 0:
                all_producers_done.set()

    # -------------------------------------------------------------------------
    # LUỒNG CONSUMER
    # -------------------------------------------------------------------------
    def consumer_worker(consumer_id: str) -> None:
        while True:
            # Nếu tất cả Producer đã xong và đã lấy đủ số item thì kết thúc
            with consumed_lock:
                if len(consumed_items) >= total_expected_items:
                    break

            # Gọi consume với non-blocking (timeout=0.0)
            result = shm.consume(process_id=consumer_id, timeout=0.0)
            state = shm.get_state()

            if result.status == "SUCCESS":
                with consumed_lock:
                    consumed_items.append(result.data)
                logger.log(consumer_id, "CONSUME", "SUCCESS", state, result.detail)
                time.sleep(0.07)  # Thời gian xử lý dữ liệu tiêu thụ
            else:
                # Rơi vào trạng thái BLOCKED do buffer rỗng (Semaphore full == 0)
                # Chỉ ghi log nếu vẫn còn sản phẩm chưa xong
                if not all_producers_done.is_set() or shm.count > 0:
                    logger.log(
                        consumer_id,
                        "CONSUME",
                        "BLOCKED",
                        state,
                        f"Buffer RỖNG! [{consumer_id}] bị BLOCKED tại Semaphore full, đợi Producer ghi dữ liệu...",
                    )
                time.sleep(0.05)

    # -------------------------------------------------------------------------
    # KHỞI CHẠY CÁC THREADS ĐỒNG THỜI
    # -------------------------------------------------------------------------
    producer_threads = [
        threading.Thread(target=producer_worker, args=(f"P{i+1}",), name=f"Thread-P{i+1}")
        for i in range(num_producers)
    ]
    consumer_threads = [
        threading.Thread(target=consumer_worker, args=(f"C{j+1}",), name=f"Thread-C{j+1}")
        for j in range(num_consumers)
    ]

    start_time = time.time()

    # Khởi chạy tất cả luồng
    for t in consumer_threads:
        t.start()
    for t in producer_threads:
        t.start()

    # Chờ tất cả luồng hoàn tất (Deadlock Guard: tối đa 10 giây)
    for t in producer_threads:
        t.join(timeout=10.0)
    for t in consumer_threads:
        t.join(timeout=10.0)

    elapsed_time = time.time() - start_time
    final_state = shm.get_state()

    # -------------------------------------------------------------------------
    # KIỂM CHỨNG TÍNH ĐÚNG ĐẮN (ORACLE VERIFICATION)
    # -------------------------------------------------------------------------
    is_deadlock = any(t.is_alive() for t in producer_threads + consumer_threads)
    is_count_match = len(produced_items) == total_expected_items and len(consumed_items) == total_expected_items
    is_data_intact = sorted(produced_items) == sorted(consumed_items)
    is_buffer_clean = final_state["count"] == 0 and all(x is None for x in final_state["buffer"])
    is_mutex_released = final_state["mutex"] == 1
    is_sem_consistent = final_state["empty"] == capacity and final_state["full"] == 0

    # Kiểm tra thứ tự FIFO của từng Producer độc lập
    fifo_passed = True
    for p_idx in range(1, num_producers + 1):
        p_tag = f"P{p_idx}-"
        p_consumed = [item for item in consumed_items if item.startswith(p_tag)]
        expected_p = [f"P{p_idx}-M{k}" for k in range(1, items_per_producer + 1)]
        if p_consumed != expected_p:
            fifo_passed = False
            break

    overall_success = (
        (not is_deadlock)
        and is_count_match
        and is_data_intact
        and is_buffer_clean
        and is_mutex_released
        and is_sem_consistent
        and fifo_passed
    )

    report = {
        "total_expected": total_expected_items,
        "total_produced": len(produced_items),
        "total_consumed": len(consumed_items),
        "is_deadlock": is_deadlock,
        "is_count_match": is_count_match,
        "is_data_intact": is_data_intact,
        "is_buffer_clean": is_buffer_clean,
        "is_mutex_released": is_mutex_released,
        "is_sem_consistent": is_sem_consistent,
        "fifo_passed": fifo_passed,
        "elapsed_time": elapsed_time,
        "final_state": final_state,
    }

    # In báo cáo kết quả đối soát ra màn hình
    print("\n" + "=" * 115)
    print("                    BÁO CÁO ĐỐI SOÁT KIỂM CHỨNG TÍNH ĐÚNG ĐẮN (ORACLE VERIFICATION)")
    print("=" * 115)
    print(f"[*] Cấu hình mô phỏng: {num_producers} Producers, {num_consumers} Consumers, Buffer Capacity = {capacity}")
    print(f"[*] Tổng thời gian thực thi: {elapsed_time:.3f} giây")
    print(f"[*] Số item kỳ vọng (Expected): {total_expected_items} | Đã sản xuất: {len(produced_items)} | Đã tiêu thụ: {len(consumed_items)}")
    print("-" * 115)
    print(f"1. Kiểm tra Deadlock:               [{'PASSED' if not is_deadlock else 'FAILED'}] (Tất cả luồng đều hoàn tất bình thường)")
    print(f"2. Toàn vẹn dữ liệu (Race check):   [{'PASSED' if is_data_intact else 'FAILED'}] (100% item truyền nhận nguyên vẹn, không mất/trùng)")
    print(f"3. Thứ tự FIFO từng Producer:       [{'PASSED' if fifo_passed else 'FAILED'}] (Dữ liệu từng Producer đến đúng thứ tự tuần tự)")
    print(f"4. Trạng thái giải phóng Mutex:     [{'PASSED' if is_mutex_released else 'FAILED'}] (Mutex = 1, không có tiến trình giữ khóa vĩnh viễn)")
    print(f"5. Tính nhất quán Semaphore:        [{'PASSED' if is_sem_consistent else 'FAILED'}] (Empty = {final_state['empty']}, Full = {final_state['full']}, đúng lý thuyết OS)")
    print(f"6. Trạng thái dọn dẹp Buffer:       [{'PASSED' if is_buffer_clean else 'FAILED'}] (Mảng buffer được giải phóng toàn bộ ô nhớ về None)")
    print("=" * 115)

    if overall_success:
        print(">>> KẾT LUẬN: ĐỒ ÁN ĐẠT CHUẨN ĐỒNG BỘ HÓA - KHÔNG CÓ RACE CONDITION & DEADLOCK <<<\n")
    else:
        print(">>> CẢNH BÁO: PHÁT HIỆN LỖI ĐỒNG BỘ TRONG QUÁ TRÌNH THỰC THI <<<\n")

    return overall_success, report


def test_console_shm_simulation() -> None:
    """Hàm test tương thích với pytest."""
    success, report = run_simulation(capacity=3, items_per_producer=3, num_producers=2, num_consumers=2)
    assert success, f"Simulation thất bại: {report}"


if __name__ == "__main__":
    success, _ = run_simulation(capacity=4, items_per_producer=4, num_producers=3, num_consumers=2)
    sys.exit(0 if success else 1)
