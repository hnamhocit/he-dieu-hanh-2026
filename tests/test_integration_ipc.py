import os
import csv
import sys
import time

THU_MUC_TESTS = os.path.dirname(os.path.abspath(__file__))
THU_MUC_GOC = os.path.abspath(os.path.join(THU_MUC_TESTS, ".."))
if THU_MUC_GOC not in sys.path:
    sys.path.insert(0, THU_MUC_GOC)

try:
    from src.core.shared_memory import SharedMemory
    from src.core.message_queue import MessageQueue
    from src.core.ipc_interface import IPCStatus, IPCResult
except ImportError:
    print("LOI: Khong import duoc core. Nho dung Terminal tai thu muc goc cua Git de chay!")
    sys.exit(1)

danh_sach_log = []

thu_muc_input = os.path.join("data", "input")
thu_muc_output = os.path.join("data", "output")

def ghi_log_he_thong(file_test, buoc, hanh_dong, trang_thai, chi_tiet):
    thoi_gian = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    dong_log = {
        "Timestamp": thoi_gian,
        "TestFile": file_test,
        "Step": buoc,
        "Action": hanh_dong,
        "Status": trang_thai,
        "Detail": chi_tiet
    }
    danh_sach_log.append(dong_log)
    print(f"[{thoi_gian}] [{file_test}] [Buoc {buoc}] {hanh_dong} -> {trang_thai}: {chi_tiet}")

def chay_tung_file_kich_ban(ten_file):
    duong_dan_file = os.path.join(thu_muc_input, ten_file)
    
    if not os.path.exists(duong_dan_file):
        print(f"-> Khong tim thay file {ten_file}, tu dong bo qua.")
        return

    print(f"\n--- DANG DOC FILE CONFIG: {ten_file} ---")
    
    che_do_uu_tien = "priority" in ten_file.lower() or "slot" in ten_file.lower()
    
    bo_nho_shm = SharedMemory(capacity=5)
    hang_doi_mq = MessageQueue(capacity=5, is_priority=che_do_uu_tien)

    try:
        with open(duong_dan_file, mode="r", encoding="utf-8") as f:
            doc_csv = csv.DictReader(f)
            
            stt = 1
            for dong in doc_csv:
                buoc = dong.get("Step", str(stt))
                hanh_dong = dong.get("Action", "UNKNOWN").upper()
                payload = dong.get("Payload", "Goi tin mac dinh")
                loai_loi = dong.get("FaultType", "NONE").upper()
                
                try:
                    id_goi = int(dong.get("ID", stt))
                    prior = int(dong.get("Priority", 0) or 0)
                    delay = int(dong.get("DelayMS", 0) or 0)
                except (ValueError, TypeError):
                    id_goi = stt
                    prior = 0
                    delay = 0

                item_data = {
                    "id": id_goi,
                    "sender": f"SV_Process_{buoc}",
                    "receiver": "Core_System",
                    "message": payload,
                    "delay_ms": delay,
                    "priority": prior,
                    "simulate_error": loai_loi,
                    "mechanism": "SHARED_MEMORY" if "SHM" in hanh_dong else "MESSAGE_QUEUE"
                }

                if hanh_dong in ["WRITE_SHM", "PRODUCE_SHM"]:
                    ket_qua = bo_nho_shm.produce(item=item_data, process_id=f"SV_SHM_{buoc}", timeout=0.0)
                    
                    if ket_qua.success:
                        ghi_log_he_thong(ten_file, buoc, hanh_dong, "SUCCESS", f"Ghi SHM ok. Hien tai co: {bo_nho_shm.count}/5 phan tu.")
                    else:
                        ghi_log_he_thong(ten_file, buoc, hanh_dong, ket_qua.status, f"Bi chan ghi: {ket_qua.detail}")

                elif hanh_dong in ["SEND_MQ", "PRODUCE_MQ"]:
                    ket_qua = hang_doi_mq.produce(item=item_data, process_id=f"SV_MQ_{buoc}", timeout=0.0)
                    
                    if ket_qua.success:
                        ghi_log_he_thong(ten_file, buoc, hanh_dong, "SUCCESS", f"Gui MQ ok. Hien tai co: {hang_doi_mq.count}/5 phan tu.")
                    else:
                        ghi_log_he_thong(ten_file, buoc, hanh_dong, ket_qua.status, f"Bi chan gui: {ket_qua.detail}")
                
                elif hanh_dong in ["INIT_SYSTEM", "SETUP"]:
                    ghi_log_he_thong(ten_file, buoc, hanh_dong, "SUCCESS", "He thong da san sang chay kich ban.")
                
                else:
                    ghi_log_he_thong(ten_file, buoc, hanh_dong, "SKIPPED", f"Hanh dong khong xac dinh: {hanh_dong}")

                if loai_loi != "NONE" and loai_loi != "DELAY":
                    ghi_log_he_thong(ten_file, buoc, f"BOM_LOI_{loai_loi}", "CRASH_SUCCESS", f"Mo phong tinh huong loi: {loai_loi}")

                stt += 1
                time.sleep(0.01)

    except Exception as e:
        ghi_log_he_thong(ten_file, "SYSTEM", "LOI_XU_LY", "CRITICAL", str(e))

def xuat_bao_cao_csv():
    if not os.path.exists(thu_muc_output):
        os.makedirs(thu_muc_output, exist_ok=True)

    file_out = os.path.join(thu_muc_output, "integration_trace_report.csv")
    tieu_de = ["Timestamp", "TestFile", "Step", "Action", "Status", "Detail"]

    try:
        with open(file_out, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=tieu_de)
            writer.writeheader()
            writer.writerows(danh_sach_log)
        print(f"\n[XUAT FILE OK] Kich ban kiem thu hoan thanh! Da ghi bao cao tai: {file_out}")
    except PermissionError:
        print(f"\n[LOI] Khong ghi duoc file vi ban dang mo file {file_out} bang Excel!")
    except Exception as e:
        print(f"Loi xuat file: {e}")

if __name__ == "__main__":
    print("=== BAT DAU KICH BAN KIEM THU TICH HOP IPC ===")
    
    danh_sach_file_test = [
        "edge_empty.csv",
        "invalid_format.csv",
        "normal_config.csv",
        "sample_config.csv",
        "sample_messages.csv",
        "test_slots.csv",
        "test_slots_edges.csv"
    ]
    
    for file in danh_sach_file_test:
        chay_tung_file_kich_ban(file)
        
    xuat_bao_cao_csv()
    print("\n=== KET THÚC CHUONG TRINH TEST IPC ===")