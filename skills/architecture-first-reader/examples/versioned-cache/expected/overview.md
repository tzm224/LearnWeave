# EpochGate：撤销在途结果的回填资格

这份**原创虚构材料**的核心 Idea 是：读取取得了一个值，并不意味着它现在仍有资格进入缓存；写入改变代际，读取在发布结果时重新检查资格。[n:epoch_permission] [s:s_state]

[理解主线](knowledge_spine.md) · [架构与设计决策](architecture_analysis.md) · [可迁移思想](design_patterns.md) · [原文地图](document_map.md) · [L1 知识图](knowledge_graph.mmd) · [节点数据](knowledge_nodes.json) · [关系数据](knowledge_graph.json)

## 为什么需要它

“写成功后删除缓存”有一个缺口：早先启动的读取可能已经拿到了旧值，却在删除之后才回填。后续新读就又命中了旧值。删除了现存副本，并没有撤销在途结果。[n:stale_fill] [s:s_race] [来源](document_map.md#source-s_race)

讨论范围是单进程、单键、唯一写入口；存储原子读写且不存在提交状态未知的失败。[n:single_gateway] [s:s_scope] [边界](architecture_analysis.md#node-single_gateway)

## Idea 如何变成架构

所有同键请求共享代际与短锁。读在锁内记录偶数代际，去锁外取值，回来再在锁内比较代际并发布。写在存储 I/O 前把代际改成奇数并清空缓存，完成后再推进为偶数。[n:epochgate] [s:s_read] [s:s_write]

例如读 R 保存代际 0 并取到 A；写 W 将值改成 B，把代际推进到 2。R 回来时发现 `2 != 0`，丢弃 A 并重试。[来源](document_map.md#source-s_trace)

## 为什么采用这些设计

**原文选择**将比较和发布放在同一临界区：如果两者分离，写可能插在中间，旧值仍会被放入没有独立版本标签的缓存。另一方面，存储 I/O 放在锁外，以免慢 I/O 长时间占用状态锁。[n:publish_guard] [s:s_trace] [s:s_cost] [深入设计推理](architecture_analysis.md#node-publish_guard)

## 获得什么，付出什么

在所列假设下，协议阻止旧回填成为写后新读的有效缓存命中。材料提供手工执行序列和局部不变式论证，**没有运行实验，也没有性能测量**。它可能丢弃并重做存储读；写频繁时没有完成时限，不提供跨进程一致性。[n:old_fill_rejected] [n:retry_cost] [s:s_invariant] [s:s_cost] [证据范围](architecture_analysis.md#node-old_fill_rejected)

## 值得迁移什么

**AI 归纳**：把耗时计算的结果视为“有条件可提交”，在生效点复核前提。前提是变化可被检测、检查与发布可原子协调、结果可以安全丢弃；已产生不可撤销副作用时不能直接套用。[n:validate_at_commit] [可迁移模式及边界](design_patterns.md)

已检查原材料全部 64 行；无外部图片或附录缺口。此例用于展示技能产物，不代表真实系统验证。
