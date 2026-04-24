import os
import time
try:
    from mooncake.store import MooncakeDistributedStore
except ImportError:
    print("Import failed")
    exit(1)

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
        print(f"Init failed: {ret}")
        return

    print("[*] Starting verification reads (batch)...")
    keys = [f"offload_stress/chunk_{i:03d}" for i in range(8)]
    results = store.get_batch(keys)
    for i, data in enumerate(results):
        key = keys[i]
        if data is not None and len(data) > 0:
            print(f"[*] {key}: Success! Size: {len(data)}")
        else:
            print(f"[*] {key}: Failed!")

    print("[*] Starting verification reads (batch_get_into)...")
    import ctypes
    chunk_size = 134217728
    
    def get_ptr(obj):
        return ctypes.addressof(ctypes.c_char.from_buffer(obj))
        
    buffers = [bytearray(chunk_size) for _ in range(2)]
    ptrs = [get_ptr(b) for b in buffers]
    sizes = [chunk_size for _ in range(2)]
    keys_subset = keys[:2]
    
    # This should trigger batch_get_into_internal
    retes = store.batch_get_into(keys_subset, ptrs, sizes)
    print(f"[*] batch_get_into results: {retes}")

    print("[*] Starting verification reads (batch_get_into_multi_buffers)...")
    # batch_get_into_multi_buffers(keys, all_buffers, all_sizes, prefer_same_node)
    # all_buffers is List[List[uintptr_t]]
    all_ptrs = [[p] for p in ptrs]
    all_sizes = [[s] for s in sizes]
    retes2 = store.batch_get_into_multi_buffers(keys_subset, all_ptrs, all_sizes, True)
    print(f"[*] batch_get_into_multi_buffers results: {retes2}")

    print("[*] Verification finished.")
    store.close()

if __name__ == "__main__":
    main()
