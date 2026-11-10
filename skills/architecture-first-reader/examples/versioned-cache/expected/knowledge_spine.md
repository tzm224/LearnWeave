# EpochGate：从故障走到设计边界

下面是分析者重建的学习顺序，不是对作者写作意图的事实陈述。它与 Graph 共用节点 ID；先回答为什么需要这套协议，再考虑具体实现和迁移。

## 1. 为什么删除以后还能读到旧值 [n:stale_fill]

从 S2 的具体故障开始：旧读已经拿到 A，写 B 并删除缓存，旧读随后又填入 A。问题不在删除是否执行，而在删除没能影响在途结果。先掌握这个反例，无需阅读全部代码。[s:s_race] [来源](document_map.md#source-s_race) · [展开](architecture_analysis.md#node-stale_fill)

## 2. 这是什么范围内的问题 [n:single_gateway]

界定刚才的问题在哪个并发和存储模型下讨论：同一进程内的请求共享状态，全部写入通过同一入口。绕过入口的写无法被局部代际感知。认识边界就够，不把目标扩大成分布式一致性。[s:s_scope] [来源](document_map.md#source-s_scope) · [展开](architecture_analysis.md#node-single_gateway)

## 3. 从删除副本转向撤销资格 [n:epoch_permission]

边界清楚后，再理解核心转变：结果有没有算完，与结果现在能不能进入缓存是两个问题。保存代际是记录资格，发布前复核是检查资格有没有被撤销。这是作者明确表达的 Idea。[s:s_state] [来源](document_map.md#source-s_state) · [展开](architecture_analysis.md#node-epoch_permission)

## 4. 把资格放进读写路径 [n:epochgate]

接下来要回答谁维护资格。读写共享短锁与代际；写先撤销旧资格，读在锁外取值后再回来申请发布。沿一个读请求走完整条路径，应能够解释状态操作与 I/O 的边界。[s:s_read] [s:s_write] [来源](document_map.md#source-s_read) · [展开](architecture_analysis.md#node-epochgate)

## 5. 为什么比较和发布必须在一起 [n:publish_guard]

有版本字段还不够：若比较后允许写插入、之后才发布，检查就过期了。因为本例缓存不另存版本标签，后来的读会命中那个旧值。要理解这种交错，而不只是记住“加锁”。[s:s_trace] [来源](document_map.md#source-s_trace) · [展开](architecture_analysis.md#node-publish_guard)

## 6. 哪些证据支持了什么结果 [n:old_fill_rejected]

机制清楚后，区分展示的执行序列与条件性不变式。它们支持所列模型下的旧回填隔离；没有支持性能提高、真实实现已经正确或分布式强一致。核心结论可停留在宏观层，想检查证明再深入 L3。[s:s_invariant] [来源](document_map.md#source-s_invariant) · [展开证据](architecture_analysis.md#node-old_fill_rejected)

## 7. 并发换来了什么成本 [n:retry_cost]

确认保证后再评价设计：I/O 不长时间占用状态锁，却可能做了无用的读取并重试。高频写下的读完成时限仍未解决，原文也没有性能实验比较优劣。[s:s_cost] [来源](document_map.md#source-s_cost) · [展开](architecture_analysis.md#node-retry_cost)

## 8. 哪部分可以带到别的问题里 [n:validate_at_commit]

最后抽象“生效前复核前提”。这是 AI 归纳，必须连同变化检测、原子协调和可丢弃结果等条件一起迁移；不是给所有并发问题套一个版本号。[s:s_read] [s:s_trace] [模式及失效边界](design_patterns.md) · [展开](architecture_analysis.md#node-validate_at_commit)

[返回总览](overview.md) · [查看 L1 图谱](knowledge_graph.mmd)
