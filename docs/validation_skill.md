# Mooncake SSD Offload 验证技能总结

## 核心挑战
Mooncake 在内存不足时会将数据淘汰至本地 SSD (`LOCAL_DISK`) 或远端磁盘 (`DISK`)。验证逻辑需要确保：
1. **优先级逻辑**: 显式优先选择 `LOCAL_DISK` 路径而非 `DISK`。
2. **数据一致性**: 淘汰过程不损坏数据内容。

## 验证工作流

### 1. 环境准备
- **内存分段限制**: 必须在启动客户端时通过 `--global_segment_size` 严格限制内存，使其小于测试写入量，从而诱发淘汰。
- **SSD 路径导出**: 导出 `MOONCAKE_OFFLOAD_FILE_STORAGE_PATH` 环境变量。

### 2. 触发淘汰 (Eviction)
- 使用大量 `put` 操作。例如，对于 5GB 限额，写入 6.25GB 数据。
- **关键技巧**: 写入数据应具有唯一可识别性（如基于索引的特征字符），以便后续校验。

### 3. 代码插桩验证 (Instrumentation)
- 在 `src/real_client.cpp` 的 `GetPreferredReplica` 调用后添加日志，打印 `has_memory`, `has_local_disk`, `has_disk` 的布尔值，以及最终 `selected` 的副本类型。
- **模拟边界情况**: 若环境默认只有单一磁盘副本，可在代码中 `mock` 另一个副本的存在，强制抉择逻辑执行。

### 4. 读取 API 全覆盖
必须测试以下所有受影响的 `RealClient` 内部函数：
- `get_buffer_internal`
- `batch_get_buffer_internal`
- `batch_get_into_internal`
- `batch_get_into_multi_buffers_internal`

### 5. 一致性检查
- 从 Python 端读取分片并进行 `bytes` 对比。
- 采用多点采样（Head, Middle, Tail）提升检查效率。

## 常见问题
- **写入失败**: 若 `put` 返回 -200 (Insufficient Space)，通常是因为 SSD 回收速度赶不上写入速度，需在脚本中加入 `sleep` 后重试。
- **库依赖**: 在 Linux 下运行测试脚本时，需确保 `LD_LIBRARY_PATH` 包含了 mooncake 编译出的 `.so` 以及 AWS/RDMA 等依赖库。

## 技能进阶：应对高压写入下的验证
1. **处理 -200 写入异常**: 在内存极小的环境下，大量写入会触发频繁淘汰。若写入速度远超淘汰速度，Master 会拒绝新的 `put`。
    - **对策**: 测试脚本必须实现**指数退避或持续重试**，直到数据成功上云/落盘。
2. **全量一致性审计**: 抽样检查在处理大批量分片时可能遗漏边缘 case。
    - **推荐方法**: 使用 `bytes` 直接对比或计算 SHA256。在 Python 中，`data == expected_bytes` 对于百兆级别的数据比对非常高效。
3. **日志关联分析**: 使用单一聚合文件记录所有进程时间线，是定位“读取空数据”到底是“未写入”还是“读取报错”的关键。
