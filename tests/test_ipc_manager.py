"""
Kiểm thử bộ điều phối vòng đời tiến trình và tài nguyên IPC (IPCManager).
Tasks: HDH-93
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core import (
    IPCManager,
    LifecycleState,
    ProcessRole,
    ProcessStatus,
    SharedMemory,
    MessageQueue,
    IPCStatus,
)


class TestIPCManagerLifecycle:
    """Kiểm tra máy trạng thái vòng đời: Start, Pause, Resume, Stop, Reset."""

    def test_initial_state(self):
        mgr = IPCManager(mechanism="SHARED_MEMORY", capacity=5)
        assert mgr.state == LifecycleState.IDLE
        assert not mgr.is_running
        assert not mgr.is_paused
        assert isinstance(mgr.mechanism, SharedMemory)
        mgr.cleanup()

    def test_invalid_mechanism_raises(self):
        with pytest.raises(ValueError):
            IPCManager(mechanism="INVALID_MECHANISM")

        with pytest.raises(TypeError):
            IPCManager(mechanism=12345)

    def test_lifecycle_transitions(self):
        mgr = IPCManager(mechanism="MESSAGE_QUEUE", capacity=5)

        # 1. Start: IDLE -> RUNNING
        assert mgr.start() is True
        assert mgr.state == LifecycleState.RUNNING
        assert mgr.is_running is True

        # Calling start again when RUNNING returns False
        assert mgr.start() is False

        # 2. Pause: RUNNING -> PAUSED
        assert mgr.pause() is True
        assert mgr.state == LifecycleState.PAUSED
        assert mgr.is_paused is True

        # Calling pause again when PAUSED returns False
        assert mgr.pause() is False

        # 3. Resume: PAUSED -> RUNNING
        assert mgr.resume() is True
        assert mgr.state == LifecycleState.RUNNING
        assert not mgr.is_paused

        # 4. Stop: RUNNING -> STOPPED
        assert mgr.stop(timeout=1.0) is True
        assert mgr.state == LifecycleState.STOPPED

        # 5. Reset: STOPPED -> RESET -> IDLE
        assert mgr.reset() is True
        assert mgr.state == LifecycleState.IDLE

        mgr.cleanup()

    def test_context_manager(self):
        with IPCManager(mechanism="SHARED_MEMORY", capacity=3) as mgr:
            assert mgr.is_running
            res = mgr.produce("msg_1", process_id="Proc_P")
            assert res.success is True
        # Sau khi thoát with, cleanup() đã được gọi
        assert mgr.state == LifecycleState.TERMINATED


class TestIPCManagerOrchestration:
    """Kiểm tra điều phối Producer và Consumer."""

    def test_manual_produce_and_consume(self):
        mgr = IPCManager(mechanism="SHARED_MEMORY", capacity=3)
        mgr.start()

        # Produce
        res1 = mgr.produce({"message": "Hello World"}, process_id="Prod_1")
        assert res1.success is True

        # Check PCB
        tbl = mgr.get_process_table()
        prod_pcb = next(p for p in tbl if p["process_id"] == "Prod_1")
        assert prod_pcb["role"] == ProcessRole.PRODUCER.value
        assert prod_pcb["items_count"] == 1

        # Consume
        res2 = mgr.consume(process_id="Cons_1")
        assert res2.success is True
        assert res2.data["message"] == "Hello World"

        tbl2 = mgr.get_process_table()
        cons_pcb = next(p for p in tbl2 if p["process_id"] == "Cons_1")
        assert cons_pcb["role"] == ProcessRole.CONSUMER.value
        assert cons_pcb["items_count"] == 1

        mgr.cleanup()

    def test_spawn_workers_produce_consume(self):
        mgr = IPCManager(mechanism="MESSAGE_QUEUE", capacity=10)
        mgr.start()

        items_to_send = [f"pkg_{i}" for i in range(5)]
        received_items = []

        # Khởi chạy Producer và Consumer ngầm
        th_prod = mgr.spawn_producer("Worker_P", items=items_to_send, delay_ms=1.0)
        th_cons = mgr.spawn_consumer(
            "Worker_C",
            count=5,
            delay_ms=2.0,
            on_item_received=lambda it: received_items.append(it.message if hasattr(it, "message") else str(it)),
        )

        th_prod.join(timeout=3.0)
        th_cons.join(timeout=3.0)

        assert len(received_items) == 5
        assert received_items == items_to_send

        state = mgr.get_system_state()
        assert state["total_processes"] == 2
        assert state["active_workers"] == 0

        mgr.cleanup()

    def test_pause_suspends_workers(self):
        mgr = IPCManager(mechanism="SHARED_MEMORY", capacity=5)
        mgr.start()

        received_count = 0

        def on_recv(_):
            nonlocal received_count
            received_count += 1

        th_c = mgr.spawn_consumer("Worker_C", count=5, delay_ms=5.0, on_item_received=on_recv)

        # Gửi 1 item trước khi pause
        mgr.produce("pkg_1", process_id="P1")
        time.sleep(0.05)

        # Pause hệ thống
        mgr.pause()
        assert mgr.is_paused

        # Khi pause, sản xuất thêm 2 item nhưng consumer đang bị chặn bởi pause_event
        # (Lưu ý: hàm produce trực tiếp từ main thread cũng kiểm tra pause_event nếu gọi)
        # Kiểm tra PCB status khi pause
        tbl = mgr.get_process_table()
        for p in tbl:
            assert p["status"] == ProcessStatus.PAUSED.value

        # Resume lại
        mgr.resume()
        assert mgr.is_running

        # Gửi tiếp các item còn lại
        for i in range(2, 6):
            mgr.produce(f"pkg_{i}", process_id="P1")

        th_c.join(timeout=3.0)
        assert received_count == 5

        mgr.cleanup()


class TestIPCManagerResourceCleanup:
    """Kiểm tra giải phóng 100% tài nguyên khi thoát đột ngột (Fail-safe)."""

    def test_cleanup_stops_threads_and_cleans_memory(self):
        mgr = IPCManager(mechanism="SHARED_MEMORY", capacity=4)
        mgr.start()

        # Tạo dữ liệu đầy bộ đệm
        for i in range(4):
            mgr.produce(f"item_{i}", process_id="Proc_Fill")

        assert mgr.mechanism.count == 4

        # Chạy worker vô tận (chờ consume)
        th = mgr.spawn_consumer("Hanging_Consumer", count=100, delay_ms=50.0)
        assert th.is_alive()

        # Giả lập thoát đột ngột: gọi cleanup()
        mgr.cleanup()

        assert mgr.state == LifecycleState.TERMINATED
        # Chờ thread kết thúc sau khi cleanup đánh thức shutdown
        th.join(timeout=1.0)
        assert not th.is_alive()

        # Bộ nhớ Shared Memory đã được reset giải phóng
        assert mgr.mechanism.count == 0
        assert mgr.mechanism.is_empty

        # Idempotent: gọi lại cleanup() không gây lỗi
        mgr.cleanup()
        assert mgr.state == LifecycleState.TERMINATED
