# EpochGate：原文地图与证据索引

原件：[EpochGate 原创虚构材料](../source.md)。JSON 中的 `examples/versioned-cache/source.md` 相对技能根目录；本文件使用相对链接以便整个技能移动后仍可阅读。

## 原始组织

- S1（5–11 行）界定服务接口、保证和前提。
- S2（13–22 行）给出删除基线的具体反例。
- S3（24–42 行）定义状态与读写协议，落实资格思想。
- S4（44–50 行）重放失败交错，并解释原子发布的作用。
- S5（52–56 行）用局部不变式支持条件性保证。
- S6（58–64 行）讨论成本、长锁替代方案及缺失的保证。

这是来源组织；[理解主线](knowledge_spine.md) 从故障现象开始，再引入边界与资格思想，没有机械复用章节顺序。

## 实际阅读范围

检查全部 64 行，包括 1–3 行的虚构材料声明，S3 的节标题、状态、读写规则和 S6 的全部限制。不存在未获取图表、附录或外部实验。原文证据仅为手工推演和协议论证；“完整阅读”不代表协议已被形式验证。

## 来源索引

<a id="source-s_scope"></a>

### 接口和边界 [s:s_scope]

[原件](../source.md) — lines 5–11，S1。primary；包括唯一写入口、存储语义、目标保证及失败假设。

<a id="source-s_race"></a>

### 基线反例 [s:s_race]

[原件](../source.md) — lines 13–22，S2。primary；四步序列说明删除之后仍可能回填旧值，不能推断发生率。

<a id="source-s_state"></a>

### 共享状态与资格思想 [s:s_state]

[原件](../source.md) — lines 26–30，S3.1。primary；代际、短锁、无独立版本标签的缓存值，以及有条件的回填资格。

<a id="source-s_read"></a>

### 读取协议 [s:s_read]

[原件](../source.md) — lines 32–36，S3.2。primary；检查缓存、记录代际、锁外取值、原子复核发布或重试。

<a id="source-s_write"></a>

### 写入协议 [s:s_write]

[原件](../source.md) — lines 38–42，S3.3。primary；奇数写入阶段、清缓存、写完成推进，以及确定未提交时的失败处理。

<a id="source-s_trace"></a>

### 执行序列与竞态窗口 [s:s_trace]

[原件](../source.md) — lines 44–50，S4。primary；代际 0→1→2 的例子，以及拆开检查和发布的反例。手工推演，不是运行记录。

<a id="source-s_invariant"></a>

### 条件性不变式 [s:s_invariant]

[原件](../source.md) — lines 52–56，S5。primary；支持单键旧回填隔离，不覆盖具体语言实现或分布式强一致。

<a id="source-s_cost"></a>

### 代价、替代与边界 [s:s_cost]

[原件](../source.md) — lines 58–64，S6。primary；额外锁操作、重试、长锁方案、TTL 的不足，以及没有保证的情况。

[返回总览](overview.md)
