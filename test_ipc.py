import time
import threading
from ipc_manager import MessagePacket, MessageQueueCore

def run_console_test():
    print("==================================================")
    print("  KIỂM TRA TRẠNG THÁI HÀNG ĐỢI ĐẦY / RỖNG (HDH-29)")
    print("==================================================")
    
    q = MessageQueueCore(capacity=2)
    
    print("\n--- [Test 1] Thử dequeue ở chế độ Non-blocking khi hàng đợi rỗng ---")
    item = q.dequeue(timeout=0)
    print(f"Kết quả dequeue (timeout=0): {item} (Đúng nếu là None)")
    
    print("\n--- [Test 2] Đưa gói tin vào cho đến khi đầy hàng đợi ---")
    pkt1 = MessagePacket(1, "Proc_A", "Proc_B", "Tin nhắn số 1")
    pkt2 = MessagePacket(2, "Proc_A", "Proc_B", "Tin nhắn số 2")
    
    print(f"Enqueue pkt1: {q.enqueue(pkt1, timeout=0)}")
    print(f"Enqueue pkt2: {q.enqueue(pkt2, timeout=0)}")
   
    pkt3 = MessagePacket(3, "Proc_A", "Proc_B", "Tin nhắn số 3 (Quá tải)")
    print(f"Enqueue pkt3 khi hàng đợi ĐẦY (timeout=0): {q.enqueue(pkt3, timeout=0)} (Đúng nếu là False)")
    
    print("\n--- [Test 3] Kiểm tra cơ chế Blocking (Condition Variable) ---")
    
    def delayed_consumer():
        print("   [Consumer Thread] Đang ngủ 1.5 giây trước khi lấy tin...")
        time.sleep(1.5)
        consumed = q.dequeue() 
        print(f"   [Consumer Thread] Đã lấy ra: '{consumed.message}' -> Hàng đợi đã có chỗ trống!")
    t = threading.Thread(target=delayed_consumer)
    t.start()
    print("Main Thread: Đang cố gắng đẩy pkt3 vào (Sẽ bị BLOCK chờ chỗ trống)...")
    start_time = time.time()
    success = q.enqueue(pkt3, timeout=None)
    elapsed = time.time() - start_time
    
    print(f"Main Thread: Đẩy pkt3 thành công? {success} (Mất {elapsed:.2f} giây chờ)")
    
    t.join()
    print("\n==================================================")
    print("       KIỂM TRA CONSOLE HOÀN TẤT THÀNH CÔNG!       ")
    print("==================================================")

if __name__ == "__main__":
    run_console_test()