import os
import time

try:
    from mooncake.store import MooncakeDistributedStore, ReplicateConfig
except ImportError:
    print("请确保已安装 mooncake 库或设置了 PYTHONPATH")
    exit(1)

def main():
    # --- 1. 配置信息 ---
    MASTER_ADDR = "127.0.0.1:50051"
    REAL_CLIENT_SEGMENT = "real_client" 
    
    # 模拟器设置
    store = MooncakeDistributedStore()
    ret = store.setup(
        local_hostname="simulation_script_node",
        metadata_server="P2PHANDSHAKE",
        global_segment_size=0,
        local_buffer_size=256 * 1024 * 1024,  # 256MB Staging 中转空间
        protocol="tcp",
        rdma_devices="lo",
        master_server_addr=MASTER_ADDR
    )
    
    if ret != 0:
        print(f"初始化失败，错误码: {ret}")
        return

    # --- 2. 写入压力测试 ---
    # 5GB = 40 * 128MB. 我们写 50 个分片确保触发淘汰。
    NUM_CHUNKS = 50
    CHUNK_SIZE_MB = 128 
    
    config = ReplicateConfig()
    config.preferred_segment = REAL_CLIENT_SEGMENT

    print(f"[*] 开始一致性压力测试：分 {NUM_CHUNKS} 次写入，每次 {CHUNK_SIZE_MB}MB")

    for i in range(NUM_CHUNKS):
        key = f"offload_stress/chunk_{i:03d}"
        # 生成唯一数据：每个 key 使用不同的字符填充
        char = ord('A') + (i % 26)
        chunk_data = bytes([char]) * (CHUNK_SIZE_MB * 1024 * 1024)
        
        print(f"[*] [{i+1}/{NUM_CHUNKS}] 正在写入 {key} (char={chr(char)})...", end="", flush=True)
        
        start = time.time()
        ret = store.put(key, chunk_data, config)
        
        if ret == 0:
            elapsed = time.time() - start
            print(f" 成功! 耗时: {elapsed:.2f}s")
        else:
            print(f" 失败 (错误码: {ret})")
            if ret in [-200, -10, -600, -1300]:
                print(f"[!] 内存压力，等待 10 秒...")
                time.sleep(10)
                ret = store.put(key, chunk_data, config)
                if ret == 0: print("    -> 重试成功！")
                else: print(f"    -> 重试失败 (err={ret})")

    print("\n[+] 写入流程结束。")
    time.sleep(5)
    store.close()

if __name__ == "__main__":
    main()
