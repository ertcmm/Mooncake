import os
import time
import ctypes

try:
    from mooncake.store import MooncakeDistributedStore
except ImportError:
    print("请确保已安装 mooncake 库或设置了 PYTHONPATH")
    exit(1)

def verify_data_full(data, expected_char, key):
    if data is None:
        print(f"[*] {key}: FAILED (Data is None)")
        return False
    
    expected_size = 128 * 1024 * 1024
    if len(data) != expected_size:
        print(f"[*] {key}: FAILED (Size mismatch: expected {expected_size}, got {len(data)})")
        return False

    # 全量字节比对 (最慢但最严谨)
    # 我们可以通过 memoryview 和 np.frombuffer 来加速，但这里保持简单
    # 或者直接对比整个 bytes 对象
    expected_data = bytes([expected_char]) * expected_size
    if data != expected_data:
        # 如果不匹配，找出第一个不匹配的位置
        mismatch_idx = -1
        for i in range(len(data)):
            if data[i] != expected_char:
                mismatch_idx = i
                break
        print(f"[*] {key}: FAILED (Content mismatch at index {mismatch_idx}: expected {expected_char}, got {data[mismatch_idx]})")
        return False

    print(f"[*] {key}: SUCCESS (Full Data Verified, char={chr(expected_char)})")
    return True

def main():
    MASTER_ADDR = "127.0.0.1:50051"
    store = MooncakeDistributedStore()
    ret = store.setup(
        local_hostname="verification_node",
        metadata_server="P2PHANDSHAKE",
        global_segment_size=0,
        local_buffer_size=256 * 1024 * 1024,
        protocol="tcp",
        rdma_devices="lo",
        master_server_addr=MASTER_ADDR
    )
    
    if ret != 0:
        print(f"初始化失败: {ret}")
        return

    print("\n[+] 开始全量数据一致性验证...")
    
    NUM_CHUNKS = 50
    all_success = True
    for i in range(NUM_CHUNKS):
        key = f"offload_stress/chunk_{i:03d}"
        expected_char = ord('A') + (i % 26)
        
        start = time.time()
        data = store.get(key)
        elapsed = time.time() - start
        
        if not verify_data_full(data, expected_char, key):
            all_success = False
        else:
            print(f"    (Read took {elapsed:.2f}s)")

    if all_success:
        print("\n[✔] 所有 50 个分片的全量数据一致性验证通过！")
    else:
        print("\n[✘] 部分分片数据不一致，请检查系统逻辑。")

    store.close()

if __name__ == "__main__":
    main()
