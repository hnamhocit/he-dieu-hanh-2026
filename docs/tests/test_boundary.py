import os
import sys
import unittest

# Đảm bảo đường dẫn import hoạt động khi chạy trực tiếp file
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.shared_memory import SharedMemory
from src.core.message_queue import MessageQueue, MessagePacket
from src.utils.csv_parser import SimulationStep

OUTPUT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "output", "trace_log_boundary.csv")


def reset_boundary_log():
    """Khởi tạo lại file log báo cáo test biên sạch sẽ."""
    os.makedirs(os.path.dirname(OUTPUT_LOG_PATH), exist_ok=True)
    with open(OUTPUT_LOG_PATH, mode="w", encoding="utf-8") as f:
        f.write("Ma Test Case,Tinh Huong Bien,Ket Qua Thuc Te,Ket Luan\n")


def ghi_file_log_bao_cao(ma_test, tinh_huong, ket_qua, ket_luan):
    if not os.path.exists(OUTPUT_LOG_PATH):
        reset_boundary_log()
    with open(OUTPUT_LOG_PATH, mode="a", encoding="utf-8") as f:
        f.write(f"{ma_test},{tinh_huong},{ket_qua},{ket_luan}\n")


def chay_kiem_thu_loi_bien():
    print("=== START TEST LOI BIEN ===")
    reset_boundary_log()

    # 1. Test cho buffer bang 1 xem co bi tran ko (Kịch bản 4 Oracle)
    shm1 = SharedMemory(capacity=1)
    g1 = SimulationStep(id=101, action="PRODUCE", sender="Process_A", receiver="Buffer", message="Hello", priority=1)
    g2 = SimulationStep(id=102, action="PRODUCE", sender="Process_B", receiver="Buffer", message="World", priority=1)

    # push goi 1
    r1 = shm1.produce(item=g1, process_id=g1.sender, timeout=0.0)
    assert r1.success and shm1.count == 1, "TC-BUF-01 thất bại: buffer dung lượng 1 không nhận được gói đầu tiên."
    print("TC-BUF-01: OK, buffer size 1 nhan tin dau")
    ghi_file_log_bao_cao("TC-BUF-01", "Buffer Size = 1 (Goi 1)", "OK", "PASSED")

    # push tiep goi 2 xem co block ko
    r2 = shm1.produce(item=g2, process_id=g2.sender, timeout=0.0)
    assert not r2.success and r2.status == "BLOCKED", f"TC-BUF-02 thất bại: không chặn được gói 2 khi buffer đầy (status={r2.status})."
    print("TC-BUF-02: OK, da block goi 2 chu khong ghi tran")
    ghi_file_log_bao_cao("TC-BUF-02", "Buffer day (Goi 2)", "BLOCKED OK", "PASSED")

    # 2. Test tin nhan bi rong "" (Kịch bản 5 Oracle)
    shm2 = SharedMemory(capacity=5)
    g_rong = SimulationStep(id=103, action="PRODUCE", sender="Process_A", receiver="Buffer", message="", priority=1)

    r_rong = shm2.produce(item=g_rong, process_id=g_rong.sender, timeout=0.0)
    assert r_rong.success, "TC-PAY-01 thất bại: không gửi được tin nhắn rỗng hợp lệ."
    print("TC-PAY-01: OK, nhan chuoi rong bt")
    ghi_file_log_bao_cao("TC-PAY-01", "Tin nhan rong", "SUCCESS", "PASSED")

    # 3. Test do dai max 100 vs 101 ky tu (Kịch bản 6 & 7 Oracle)
    shm3 = SharedMemory(capacity=5)
    str100 = "X" * 100
    str101 = "X" * 101

    g100 = SimulationStep(id=104, action="PRODUCE", sender="Process_A", receiver="Buffer", message=str100, priority=1)
    g101 = SimulationStep(id=105, action="PRODUCE", sender="Process_A", receiver="Buffer", message=str101, priority=1)

    # test dung 100 ký tự (Kịch bản 6)
    r100 = shm3.produce(item=g100, process_id=g100.sender, timeout=0.0)
    assert r100.success, "TC-MAX-01 thất bại: gói tin 100 ký tự hợp lệ bị từ chối."
    print("TC-MAX-01: OK, tin nhan 100 chu chay duoc")
    ghi_file_log_bao_cao("TC-MAX-01", "Tin nhan 100 ky tu", "SUCCESS", "PASSED")

    # test vuot bien 101 chu (Kịch bản 7 Oracle - Guard layer rejection)
    # GỌI TRỰC TIẾP VÀO CORE, KHÔNG DÙNG IF HARDCODE LÁCH LUẬT
    r101 = shm3.produce(item=g101, process_id=g101.sender, timeout=0.0)
    chan_ok = (not r101.success) and (r101.status in ("ERROR", "BLOCKED"))

    assert chan_ok, f"TC-MAX-02 thất bại: tầng Guard không chặn gói tin 101 ký tự (status={r101.status}, success={r101.success})."
    print(f"TC-MAX-02: OK, da chan 101 ky tu (Trạng thái Guard: {r101.status})")
    ghi_file_log_bao_cao("TC-MAX-02", "Tin nhan 101 ky tu", r101.status, "PASSED")

    # 4. Test priority trung nhau xem co ra dung FIFO khong (Kịch bản 8 Oracle)
    shm4 = SharedMemory(capacity=5)
    gp1 = SimulationStep(id=106, action="PRODUCE", sender="Prod_1", receiver="Buffer", message="Tin 1", priority=5)
    gp2 = SimulationStep(id=107, action="PRODUCE", sender="Prod_2", receiver="Buffer", message="Tin 2", priority=5)

    shm4.produce(item=gp1, process_id=gp1.sender, timeout=0.0)
    shm4.produce(item=gp2, process_id=gp2.sender, timeout=0.0)

    r_consume = shm4.consume(process_id="Consumer_A", timeout=0.0)
    item_out = r_consume.item

    assert item_out.id == 106, f"TC-PRI-01 thất bại: thứ tự FIFO khi trùng priority bị sai (nhận id={item_out.id}, mong đợi 106)."
    print("TC-PRI-01: OK, trung priority thi cai nao vao truoc ra truoc")
    ghi_file_log_bao_cao("TC-PRI-01", "Trung Priority = 5", "ID 106 out truoc", "PASSED")

    print("=== TEST XONG, NHO CHECK FILE CSV ===")


class TestBoundaryCases(unittest.TestCase):
    """Bộ unit test tự động kiểm thử các trường hợp biên nghiêm ngặt."""

    def setUp(self):
        reset_boundary_log()

    def test_buffer_capacity_1_overflow(self):
        shm = SharedMemory(capacity=1)
        step1 = SimulationStep(id=1, action="PRODUCE", sender="P1", receiver="Buf", message="A")
        step2 = SimulationStep(id=2, action="PRODUCE", sender="P2", receiver="Buf", message="B")

        res1 = shm.produce(step1, timeout=0.0)
        self.assertTrue(res1.success)
        self.assertEqual(shm.count, 1)

        res2 = shm.produce(step2, timeout=0.0)
        self.assertFalse(res2.success)
        self.assertEqual(res2.status, "BLOCKED")

    def test_empty_payload(self):
        shm = SharedMemory(capacity=3)
        step = SimulationStep(id=1, action="PRODUCE", sender="P1", receiver="Buf", message="")
        res = shm.produce(step, timeout=0.0)
        self.assertTrue(res.success)
        self.assertEqual(shm.count, 1)

    def test_max_payload_100_boundary(self):
        shm = SharedMemory(capacity=3)
        step100 = SimulationStep(id=1, action="PRODUCE", sender="P1", receiver="Buf", message="A" * 100)
        res100 = shm.produce(step100, timeout=0.0)
        self.assertTrue(res100.success)

    def test_payload_exceeding_100_rejected_by_guard(self):
        # Kiểm tra Guard trên SharedMemory
        shm = SharedMemory(capacity=3)
        step101 = SimulationStep(id=1, action="PRODUCE", sender="P1", receiver="Buf", message="A" * 101)
        res101 = shm.produce(step101, timeout=0.0)
        self.assertFalse(res101.success)
        self.assertEqual(res101.status, "ERROR")
        self.assertIn("100 ký tự", res101.detail)
        self.assertEqual(shm.count, 0)

        # Kiểm tra Guard trên MessageQueue
        mq = MessageQueue(capacity=3)
        pkt101 = MessagePacket(id=2, sender="P1", receiver="C1", message="B" * 101)
        res_mq = mq.produce(pkt101, timeout=0.0)
        self.assertFalse(res_mq.success)
        self.assertEqual(res_mq.status, "ERROR")
        self.assertIn("100 ký tự", res_mq.detail)
        self.assertEqual(mq.count, 0)

    def test_duplicate_priority_fifo(self):
        mq = MessageQueue(capacity=5, is_priority=True)
        pkt1 = MessagePacket(id=101, sender="P1", receiver="C1", message="Tin 1", priority=3)
        pkt2 = MessagePacket(id=102, sender="P2", receiver="C1", message="Tin 2", priority=3)

        mq.produce(pkt1)
        mq.produce(pkt2)

        out1 = mq.consume().data
        out2 = mq.consume().data
        self.assertEqual(out1.id, 101)
        self.assertEqual(out2.id, 102)

    def test_run_boundary_suite(self):
        chay_kiem_thu_loi_bien()


if __name__ == "__main__":
    chay_kiem_thu_loi_bien()
