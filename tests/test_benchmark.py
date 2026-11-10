"""Kiểm tra phép đo dùng Core thật, dữ liệu lỗi và hủy chạy."""

from threading import Event
from unittest.mock import patch

import pytest

from src.core.benchmark import BenchmarkCancelled, BenchmarkConfig, run_benchmark
from src.core.ipc_interface import IPCResult


@pytest.mark.parametrize("capacity", [1, 4, 32])
def test_real_cores_deliver_all_messages(capacity):
    results = run_benchmark(BenchmarkConfig(message_count=11, capacity=capacity, repeats=2))
    assert len(results) == 4
    assert {r.mechanism for r in results} == {"SHARED_MEMORY", "MESSAGE_QUEUE"}
    for result in results:
        assert result.message_count == 11
        assert result.throughput == pytest.approx(11 / result.elapsed_seconds)
        assert 0 < result.latency_min_ms <= result.latency_avg_ms <= result.latency_max_ms


@pytest.mark.parametrize("kwargs", [
    {"message_count": 0}, {"capacity": -1}, {"repeats": 0},
    {"mechanisms": ()}, {"mechanisms": ("PIPE",)}, {"message_count": True},
])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        run_benchmark(BenchmarkConfig(**kwargs))


def test_cancel_between_runs_keeps_only_completed_results():
    cancel = Event()
    completed = []

    def on_result(result):
        completed.append(result)
        cancel.set()

    with pytest.raises(BenchmarkCancelled):
        run_benchmark(BenchmarkConfig(message_count=3), cancel, on_result)
    assert len(completed) == 1


def test_wrong_received_data_is_not_reported_as_success():
    with patch("src.core.benchmark.SharedMemory.consume", return_value=IPCResult("SUCCESS", {"id": -1})):
        with pytest.raises(RuntimeError, match="không khớp"):
            run_benchmark(BenchmarkConfig(message_count=1))


def test_cancel_inside_run_does_not_publish_partial_result():
    cancel = Event()
    completed = []

    def produce(packet):
        cancel.set()
        return IPCResult("SUCCESS")

    with patch("src.core.benchmark.SharedMemory.produce", side_effect=produce):
        with pytest.raises(BenchmarkCancelled):
            run_benchmark(BenchmarkConfig(message_count=2), cancel, completed.append)
    assert completed == []


def test_core_failure_is_reported():
    with patch("src.core.benchmark.SharedMemory.produce", return_value=IPCResult("ERROR", success=False, detail="failed")):
        with pytest.raises(RuntimeError, match="gửi thất bại"):
            run_benchmark(BenchmarkConfig(message_count=1))
