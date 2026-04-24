import os
import time

try:
    from mooncake.store import MooncakeDistributedStore, ReplicateConfig
except ImportError:
    print("请确保已安装 mooncake 库或设置了 PYTHONPATH")
    exit(1)

def main():
    MASTER_ADDR = "127.0.0.1:50051"
    REAL_CLIENT_SEGMENT = "real_client" 
    
    store = MooncakeDistributedStore()
    ret = store.setup(
        local_hostname="simulation_script_node",
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

    NUM_CHUNKS = 50
    CHUNK_SIZE_MB = 128 
    config = ReplicateConfig()
    config.preferred_segment = REAL_CLIENT_SEGMENT

    print(f"[*] 开始加强版一致性压力测试：分 {NUM_CHUNKS} 次写入")

    for i in range(NUM_CHUNKS):
        key = f"offload_stress/chunk_{i:03d}"
        char_code = ord('A') + (i % 26)
        chunk_data = bytes([char_code]) * (CHUNK_SIZE_MB * 1024 * 1024)
        
        while True:
            start = time.time()
            ret = store.put(key, chunk_data, config)
            if ret == 0:
                elapsed = time.time() - start
                print(f"[*] [{i+1}/{NUM_CHUNKS}] {key} 成功 ({chr(char_code)})")
                break
            else:
                print(f"[*] [{i+1}/{NUM_CHUNKS}] {key} 失败(err={ret})，等待 SSD 释放空间并重试...")
                time.sleep(2) # 缩短等待，多次尝试

    print("\n[+] 写入流程结束。")
    time.sleep(10) # 给 SSD Offload 留出最后的扫描时间
    store.close()

if __name__ == "__main__":
    main()
