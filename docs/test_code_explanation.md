# Mooncake SSD Offload 测试代码说明

为了验证 Mooncake 在内存淘汰场景下对本地 SSD (`LOCAL_DISK`) 的优先级调度及数据一致性，本次任务新增了一套自动化测试工具。以下是各组件的详细说明：

## 1. 模拟写入脚本 (`mooncake_simulation.py`)
该脚本的核心目标是制造内存压力，迫使 Mooncake 将数据从内存迁移到本地 SSD。

- **功能**:
    - **大规模写入**: 连续写入 50 个分片（总计 6.25GB），超过了预设的 5GB Client 内存上限。
    - **标识性数据**: 使用 `bytes([ord('A') + (i % 26)])` 为每个分片生成唯一的特征数据，便于后续一致性校验。
    - **容错处理**: 在检测到内存爆满（错误码 -200 等）时，会自动触发等待（10秒）并进行重试，确保所有分片最终都能持久化（无论是留在内存还是迁移到 SSD）。

## 2. 基础功能验证脚本 (`mooncake_verify.py`)
该脚本用于验证 `RealClient` 中四种受影响的读取 API。

- **覆盖 API**:
    - `store.get()`: 验证单缓冲区读取。
    - `store.get_batch()`: 验证批量元数据查询与数据拉取。
    - `store.batch_get_into()`: 验证零拷贝写入预分配缓冲区的逻辑。
    - `store.batch_get_into_multi_buffers()`: 验证将单 key 数据分布到多个不连续缓冲区的逻辑。
- **验证点**: 确保在代码逻辑修改后，这些 API 依然能正常工作并返回数据。

## 3. 一致性深度验证脚本 (`mooncake_verify_consistency.py`)
这是最严谨的测试环节，确保“写入”与“读取”的数据完全一致。

- **原理**: 
    - 根据分片索引计算出预期的特征字符（如 Chunk 0 -> 'A'）。
    - 读取分片数据后，执行**多点采样校验**（开头、中间、结尾）。
- **结果输出**: 清晰展示每个分片是从 `MEMORY` 还是 `LOCAL_DISK` 读取的，并输出校验结果。

## 4. 环境启动脚本 (`start_services.sh`)
配置运行测试所需的底层环境。

- **关键配置**:
    - **SSD 离线路径**: `MOONCAKE_OFFLOAD_FILE_STORAGE_PATH=/mnt/mooncake_ssd_local`。
    - **存储后端**: 激活 `bucket_storage_backend` 以支持 SSD 持久化。
    - **内存限额**: 通过 `--global_segment_size="5 GB"` 严格控制内存占用，确保 eviction 逻辑可被触发。

## 使用流程
1. 执行 `bash start_services.sh` 启动集群。
2. 运行 `python3 mooncake_simulation.py` 填充数据并触发淘汰。
3. 运行 `python3 mooncake_verify_consistency.py` 进行自动化一致性校验。

## 5. 脚本迭代更新 (2026-04-24)
为了应对高并发压力下的瞬时写入失败，对测试套件进行了以下升级：

- **mooncake_simulation.py (v2)**: 
    - 增加了 `while True` 重试逻辑。
    - 能够自动处理 `-200` 错误，确保在内存淘汰完成前不会丢弃数据。
- **mooncake_verify_consistency.py (v2)**: 
    - 放弃了抽样检查，改为 `data != expected_data` 直接比对。
    - 能够精确指出第一个不匹配字节的索引（如有）。
- **all_processes_logs.txt**: 
    - 新增了全进程日志聚合工具，将 Master、Client 和脚本输出整合，方便全局追溯。

## 6. 工程代码插桩位置 (Instrumentation Details)
为了对 commit `b75e854` 进行闭环验证，我们在 `mooncake-store/src/real_client.cpp` 中添加了以下调试逻辑：

### 6.1 副本选择调试日志
在以下四个函数中，我们在副本决策后添加了 `has_memory`, `has_local_disk`, `has_disk` 的统计逻辑及校验日志：
- `RealClient::get_buffer_internal` (~1820行)
- `RealClient::batch_get_buffer_internal` (~2140行)
- `RealClient::batch_get_into_internal` (~3350行)
- `RealClient::batch_get_into_multi_buffers_internal` (~3710行)

**插桩代码示列**:
```cpp
// 统计可用副本类型
for (const auto &r : query_result_values.replicas) {
    if (r.is_memory_replica() && r.status == ReplicaStatus::COMPLETE) has_memory = true;
    if (r.is_local_disk_replica() && r.status == ReplicaStatus::COMPLETE) has_local_disk = true;
    if (r.is_disk_replica() && r.status == ReplicaStatus::COMPLETE) has_disk = true;
}

// 决策路径校验
if (!has_memory && has_local_disk && has_disk) {
    if (replica.is_local_disk_replica()) {
        LOG(INFO) << "[CORRECT PATH] Memory evicted, LOCAL_DISK preferred.";
    } else {
        LOG(ERROR) << "[WRONG PATH] Memory evicted, but LOCAL_DISK was NOT preferred.";
    }
}
```

### 6.2 模拟测试信号 (Mocking Signal)
为了在只有单磁盘副本的环境下验证优先级逻辑，我们在上述函数中针对特定测试 key 强制注入了 `has_disk = true` 的假信号：
```cpp
if (key == "offload_stress/chunk_000" && has_local_disk) {
    has_disk = true;
    LOG(INFO) << "[MOCK] Forcing has_disk=true to verify priority logic.";
}
```
