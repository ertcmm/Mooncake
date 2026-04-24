import os
import time
import ctypes

try:
    from mooncake.store import MooncakeDistributedStore
except ImportError:
    print("请确保已安装 mooncake 库或设置了 PYTHONPATH")
    exit(1)

def get_ptr(obj):
    return ctypes.addressof(ctypes.c_char.from_buffer(obj))

def verify_data(data, expected_char, key):
    if data is None:
        print(f"[*] {key}: FAILED (Data is None)")
        return False
    
    # 首先检查大小
    expected_size = 128 * 1024 * 1024
    if len(data) != expected_size:
        print(f"[*] {key}: FAILED (Size mismatch: expected {expected_size}, got {len(data)})")
        return False

    # 检查一致性：是否全是期望的字符
    # 为了性能，我们只采样检查开头、中间、结尾
    samples = [0, expected_size // 2, expected_size - 1]
    for s in samples:
        if data[s] != expected_char:
            print(f"[*] {key}: FAILED (Consistency mismatch at index {s}: expected {expected_char}, got {data[s]})")
            return False
            
    # 全量检查 (可选，消耗 CPU)
    # if data != bytes([expected_char]) * expected_size:
    #     print(f"[*] {key}: FAILED (Full consistency check failed)")
    #     return False

    print(f"[*] {key}: SUCCESS (Size and Content Verified, char={chr(expected_char)})")
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

    print("\n[+] 开始数据一致性验证 (抽样检查)...")
    
    # 验证前 10 个分片 (这些通常还在内存或刚淘汰)
    # 验证后 10 个分片 (这些是最后写入的)
    # 验证中间几个分片 (确保全面)
    indices_to_check = list(range(10)) + list(range(20, 30)) + list(range(40, 50))
    
    all_success = True
    for i in indices_to_check:
        key = f"offload_stress/chunk_{i:03d}"
        expected_char = ord('A') + (i % 26)
        
        data = store.get(key)
        if not verify_data(data, expected_char, key):
            all_success = False

    if all_success:
        print("\n[✔] 所有检查的分片数据一致性验证通过！")
    else:
        print("\n[✘] 部分分片数据一致性验证失败，请检查逻辑。")

    store.close()

if __name__ == "__main__":
    main()
