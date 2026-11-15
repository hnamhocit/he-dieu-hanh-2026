"""
Chạy trọn bộ kiểm thử của dự án bằng MỘT lệnh (HDH-121).

Cách dùng (từ thư mục gốc của repo):
    python -m tests.run_all_tests            # chế độ nhanh (mặc định), khoảng vài chục giây
    python -m tests.run_all_tests --full     # thêm benchmark đầy đủ, chạy lâu (vài phút)

Ba nhóm kiểm thử:
    1. Unit test        : kiểm tra từng module riêng lẻ.
    2. Integration test : kiểm tra nhiều thành phần chạy cùng nhau (tải cao, GUI, điều phối).
    3. Benchmark test   : đo hiệu năng. Chế độ nhanh chỉ chạy phần kiểm tra tính đúng của
                          benchmark (tải nhỏ, không ghi file CSV). Chế độ --full chạy đo thật
                          và GHI ĐÈ data/output/son_results.csv, son_blocking.csv.

Kết thúc in bảng tổng kết. Mã thoát 0 nếu mọi test đạt, 1 nếu có lỗi.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# Tên module test thuộc từng nhóm. File nào chưa có sẽ được báo "bỏ qua", không gây lỗi.
GROUPS = [
    ("Unit test", [
        "tests.test_shared_memory",
        "tests.test_message_queue",
        "tests.test_boundary",
        "tests.test_csv_parser",
        "tests.test_csv_reader",
    ]),
    ("Integration test", [
        "tests.test_ipc_console",
        "tests.test_stress_fault",
        "tests.test_simulation_controller",
        "tests.test_main_window",
    ]),
    ("Benchmark test (kiểm tra nhanh)", [
        "tests.test_benchmark_message_queue",
        # Thêm module benchmark Shared Memory (HDH-103) vào đây khi đã có, ví dụ:
        # "tests.test_benchmark_shared_memory",
    ]),
]

# Lệnh đo đầy đủ chỉ chạy khi có --full.
FULL_BENCHMARKS = [
    [sys.executable, "-m", "tests.test_benchmark_message_queue", "--messages", "10000", "--runs", "50"],
]


def module_exists(name: str) -> bool:
    path = os.path.join(ROOT, *name.split(".")) + ".py"
    return os.path.isfile(path)


def run_group(title: str, modules: list[str]) -> dict:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    skipped = []
    for name in modules:
        if module_exists(name):
            suite.addTests(loader.loadTestsFromName(name))
        else:
            skipped.append(name)
            print(f"[bỏ qua] chưa có file: {name}")
    start = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return {
        "title": title,
        "run": result.testsRun,
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped_files": skipped,
        "seconds": time.perf_counter() - start,
    }


def run_full_benchmarks() -> int:
    print(f"\n{'=' * 70}\nBenchmark đầy đủ (--full): chạy lâu, ghi đè file CSV kết quả\n{'=' * 70}")
    code = 0
    for command in FULL_BENCHMARKS:
        if not module_exists(command[2]):
            print(f"[bỏ qua] chưa có file: {command[2]}")
            continue
        print("Chạy:", " ".join(command[1:]))
        code |= subprocess.call(command, cwd=ROOT)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Chạy trọn bộ kiểm thử (HDH-121)")
    parser.add_argument("--full", action="store_true", help="chạy thêm benchmark đầy đủ (lâu)")
    args = parser.parse_args()

    summaries = [run_group(title, modules) for title, modules in GROUPS]
    full_code = run_full_benchmarks() if args.full else 0

    print(f"\n{'=' * 70}\nTỔNG KẾT\n{'=' * 70}")
    print(f"{'Nhóm':<36} {'Số test':>8} {'Lỗi':>5} {'Hỏng':>5} {'Giây':>7}")
    total_bad = 0
    for s in summaries:
        total_bad += s["failed"] + s["errors"]
        print(f"{s['title']:<36} {s['run']:>8} {s['errors']:>5} {s['failed']:>5} {s['seconds']:>7.1f}")
    if args.full:
        print(f"{'Benchmark đầy đủ':<36} {'—':>8} {'—':>5} {'—':>5} {'—':>7}   "
              f"{'đạt' if full_code == 0 else 'LỖI'}")
    ok = total_bad == 0 and full_code == 0
    print("\nKẾT QUẢ:", "TẤT CẢ ĐẠT" if ok else "CÓ LỖI, xem chi tiết ở trên")
    if not args.full:
        print("(Chế độ nhanh. Dùng --full để chạy benchmark đầy đủ.)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())