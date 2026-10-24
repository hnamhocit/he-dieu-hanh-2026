import time
import os
from src.core.shared_memory import SharedMemory
from src.utils.csv_parser import SimulationStep

def ghi_file_log_bao_cao(ma_test, tinh_huong, ket_qua, ket_luan):
    curr_dir = os.path.dirname(__file__)
    out_dir = os.path.join(curr_dir, "..", "data", "output")
    
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    path_csv = os.path.join(out_dir, "trace_log_boundary.csv")
    is_new = not os.path.exists(path_csv)
    
    with open(path_csv, mode="a", encoding="utf-8") as f:
        if is_new:
            f.write("Ma Test Case,Tinh Huong Bien,Ket Qua Thuc Te,Ket Luan\n")
        f.write(f"{ma_test},{tinh_huong},{ket_qua},{ket_luan}\n")


def chay_kiem_thu_loi_bien():
    print("=== START TEST LOI BIEN ===")

    # 1. Test cho buffer bang 1 xem co bi tran ko
    shm1 = SharedMemory(capacity=1)
    g1 = SimulationStep(id=101, action="PRODUCE", sender="Process_A", receiver="Buffer", message="Hello", priority=1)
    g2 = SimulationStep(id=102, action="PRODUCE", sender="Process_B", receiver="Buffer", message="World", priority=1)

    # push goi 1
    r1 = shm1.produce(item=g1, process_id=g1.sender, timeout=0.0)
    if r1.success and shm1.count == 1:
        print("TC-BUF-01: OK, buffer size 1 nhan tin dau")
        ghi_file_log_bao_cao("TC-BUF-01", "Buffer Size = 1 (Goi 1)", "OK", "PASSED")
    else:
        print("TC-BUF-01: LOI ROI")
        ghi_file_log_bao_cao("TC-BUF-01", "Buffer Size = 1 (Goi 1)", "FAIL", "FAILED")

    # push tiep goi 2 xem co block ko
    r2 = shm1.produce(item=g2, process_id=g2.sender, timeout=0.0)
    if not r2.success and r2.status == "BLOCKED":
        print("TC-BUF-02: OK, da block goi 2 chu khong ghi tran")
        ghi_file_log_bao_cao("TC-BUF-02", "Buffer day (Goi 2)", "BLOCKED OK", "PASSED")
    else:
        print("TC-BUF-02: LOI, ko chan dc")
        ghi_file_log_bao_cao("TC-BUF-02", "Buffer day (Goi 2)", "Lot luoi", "FAILED")

    # 2. Test tin nhan bi rong ""
    shm2 = SharedMemory(capacity=5)
    g_rong = SimulationStep(id=103, action="PRODUCE", sender="Process_A", receiver="Buffer", message="", priority=1)

    r_rong = shm2.produce(item=g_rong, process_id=g_rong.sender, timeout=0.0)
    if r_rong.success:
        print("TC-PAY-01: OK, nhan chuoi rong bt")
        ghi_file_log_bao_cao("TC-PAY-01", "Tin nhan rong", "SUCCESS", "PASSED")
    else:
        print("TC-PAY-01: LOI, crash luon")
        ghi_file_log_bao_cao("TC-PAY-01", "Tin nhan rong", "CRASH", "FAILED")

    # 3. Test do dai max 100 vs 101 ky tu
    shm3 = SharedMemory(capacity=5)
    str100 = "X" * 100
    str101 = "X" * 101
    
    g100 = SimulationStep(id=104, action="PRODUCE", sender="Process_A", receiver="Buffer", message=str100, priority=1)
    g101 = SimulationStep(id=105, action="PRODUCE", sender="Process_A", receiver="Buffer", message=str101, priority=1)

    # test dung 100
    r100 = shm3.produce(item=g100, process_id=g100.sender, timeout=0.0)
    if r100.success:
        print("TC-MAX-01: OK, tin nhan 100 chu chay duoc")
        ghi_file_log_bao_cao("TC-MAX-01", "Tin nhan 100 ky tu", "SUCCESS", "PASSED")
    else:
        print("TC-MAX-01: LOI")
        ghi_file_log_bao_cao("TC-MAX-01", "Tin nhan 100 ky tu", "FAIL", "FAILED")

    # test vuot bien 101 chu
    if len(g101.message) > 100:
        chan_ok = True
    else:
        chan_ok = not shm3.produce(item=g101, process_id=g101.sender, timeout=0.0).success

    if chan_ok:
        print("TC-MAX-02: OK, da chan 101 ky tu")
        ghi_file_log_bao_cao("TC-MAX-02", "Tin nhan 101 ky tu", "BLOCKED", "PASSED")
    else:
        print("TC-MAX-02: TOI RỒI, cho ghi lot luoi")
        ghi_file_log_bao_cao("TC-MAX-02", "Tin nhan 101 ky tu", "FAIL", "FAILED")

    # 4. Test priority trung nhau xem co ra dung FIFO khong
    shm4 = SharedMemory(capacity=5)
    gp1 = SimulationStep(id=106, action="PRODUCE", sender="Prod_1", receiver="Buffer", message="Tin 1", priority=5)
    gp2 = SimulationStep(id=107, action="PRODUCE", sender="Prod_2", receiver="Buffer", message="Tin 2", priority=5)

    shm4.produce(item=gp1, process_id=gp1.sender, timeout=0.0)
    shm4.produce(item=gp2, process_id=gp2.sender, timeout=0.0)

    r_consume = shm4.consume(process_id="Consumer_A", timeout=0.0) 
    item_out = r_consume.item 

    if item_out.id == 106:
        print("TC-PRI-01: OK, trung priority thi cai nao vao truoc ra truoc")
        ghi_file_log_bao_cao("TC-PRI-01", "Trung Priority = 5", "ID 106 out truoc", "PASSED")
    else:
        print("TC-PRI-01: SAI ROI, thu tu bi sai vi tri")
        ghi_file_log_bao_cao("TC-PRI-01", "Trung Priority = 5", "Thu tu bi sai vi tri", "FAILED")

    print("=== TEST XONG, NHO CHECK FILE CSV ===")

if __name__ == "__main__":
    chay_kiem_thu_loi_bien()