# EpochGate：从回填资格到原子发布

以下区分作者明确给出的协议、材料中的手工/理论证据，以及分析者的迁移归纳。公式和实现细节只在解释设计必要性时展开。

<a id="node-stale_fill"></a>

## 问题发生在删除之后 [n:stale_fill]

基线中，R 先取 A，W 写 B 并删除缓存，R 随后才填入 A。删除作用于已有缓存，在途结果没有被撤销。这解释了为什么“再缩短 TTL”并不能满足目标保证：它只可能缩短错误值存活的时间。[s:s_race] [来源](document_map.md#source-s_race)

<a id="node-single_gateway"></a>

## 保证依赖什么边界 [n:single_gateway]

所有同键请求共享进程内状态，所有写经过同一服务，存储提供单键原子读写。代际不回绕，重启会消除缓存及在途任务，提交状态未知的失败被排除。与写重叠的读仍可能返回在写前选定的值；目标只禁止旧回填成为写后新读的缓存命中。[s:s_scope] [来源](document_map.md#source-s_scope)

<a id="node-epoch_permission"></a>

## Idea：结果有条件地获得发布资格 [n:epoch_permission]

原文将稳定代际视为读取的资格。写改变代际，意味着旧资格失效；读取是否完成不决定结果是否有效。这个想法还不是架构，它只确定了需要保留什么信息、在什么时刻再次核验。[s:s_state] [来源](document_map.md#source-s_state)

<a id="node-epochgate"></a>

## 架构：共享状态协调两个 I/O 路径 [n:epochgate]

入口是 `read(k)` 和 `write(k,v)`。读先在状态锁内检查是否正在写、是否有缓存；未命中则记住偶数代际 e，释放锁去存储取值，回来在同锁内检查 `epoch == e`，通过才发布。写先把偶数改为奇数并清缓存，再在锁外写存储，完成后在锁内推进为下一偶数。[s:s_read] [s:s_write]

例如 R 保存 0 并拿到 A；W 经由 1 完成写 B，再推进到 2。R 的检查失败，A 被丢弃。若没有新写打断，重试取得 B 并成功发布。这里的结构是“共享协调状态 + 锁外 I/O + 发布关口”，组件只有通过这条路径才有意义。[s:s_trace] [来源](document_map.md#source-s_trace)

<a id="node-state_gate"></a>

### 协调点 [n:state_gate]

状态锁保护代际、缓存检查与缓存发布。它没有覆盖慢存储调用，负责的是对状态变化建立共同的观察顺序。[s:s_state]

<a id="node-cache_entry"></a>

### 缓存承担复用职责 [n:cache_entry]

缓存只存值，没有独立版本标签；正确性依赖写开始清空以及发布守卫。读在偶数状态下发现非空项即可使用，因此发布守卫的原子性会直接影响后续命中。[s:s_state] [s:s_read]

<a id="node-store"></a>

### 存储承担值的持久读写 [n:store]

存储 I/O 位于状态锁之外。单键原子语义是输入假设，不是 EpochGate 自己创造的能力。[s:s_scope] [s:s_write]

<a id="node-publish_guard"></a>

## 关键决策：复核与发布不可分开 [n:publish_guard]

问题是检查过的资格可能立刻失效。作者选择在同一把锁内比较代际并发布：R 检查为 0，若释放锁让 W 推进到 2，然后 R 才发布 A，没有版本标签的缓存就又可被新读命中。因此在本例结构中，“比较与发布是一个动作”才真正落实资格规则。[s:s_read] [s:s_trace]

**Problem → Constraint → Insight → Design → Mechanism → Outcome：** 在途旧值可能晚到；I/O 不能长期持锁；结果需要保留资格；选择短锁内的原子复核发布；写推进代际使旧资格不能通过；在模型内阻断旧回填。代价是冲突读取会重做。[s:s_scope] [s:s_cost]

**替代设计：** 作者讨论了把锁覆盖整个 I/O，可阻止同样交错但增加慢 I/O 对状态检查的阻塞；作者没有给出性能实验。作者还讨论了 TTL，指出其不提供本例不变式。没有把“作者没有采用”推断成“作者已经测试并证明更差”。[s:s_cost] [来源](document_map.md#source-s_cost)

<a id="node-read_recheck"></a>

### 读取机制 [n:read_recheck]

读取在锁外取值，保留 e，并在锁内比较。失败时丢弃值并从头重试，不能只重复发布动作。[s:s_read]

<a id="node-write_fence"></a>

### 写入机制 [n:write_fence]

写开始就撤销旧资格并清缓存；写完成后才开放新的稳定代际。奇数阶段使其他读等待，也让多个写不同时操纵代际。确定未提交的失败仍推进代际，保守丢弃旧读取。[s:s_write]

<a id="node-generation"></a>

### 理解代际 [n:generation]

epoch 是逻辑身份，不是时钟。比较的是“从读取开始到发布，有没有经过写入阶段”，不是“结果是否足够新鲜”。[s:s_state]

<a id="node-split_window"></a>

### L3：拆开动作会发生什么 [n:split_window]

R 比较通过 → R 释放锁 → W 写 B、清缓存并完成 → R 写入 A。正是最后一步绕开了新的资格状态。若换成缓存项自行保存并校验版本的另一套协议，需要重新分析此反例，不能照搬本例的必要性结论。[s:s_trace] 后一句是对本例结构边界的分析者推断。

<a id="node-old_fill_rejected"></a>

## 结果与证据的范围 [n:old_fill_rejected]

作者主张：假设成立时，写之前取得旧值的读不能在写后恢复有效缓存。读先原子发布，后来的写会清掉它；写先改变代际，后来的旧读检查会失败。这是协议层面的条件性论证，不是已测试实现的报告。[s:s_invariant] [来源](document_map.md#source-s_invariant)

<a id="node-race_trace"></a>

### L3：一个反例足以否定基线保证 [n:race_trace]

S2 给出了违反目标的完整交错，足以说明基线不提供该保证。它没有说明实际故障频率。[s:s_race]

<a id="node-guarded_trace"></a>

### L3：一个成功序列不等于全面验证 [n:guarded_trace]

S4 的 0→1→2 序列说明该交错被阻断。它不能单独证明所有执行路径或真实锁实现都正确。[s:s_trace]

<a id="node-invariant_argument"></a>

### L3：不变式为何更强，也为何仍有限 [n:invariant_argument]

S5 在所列假设下把两类顺序统一起来：稳定代际中的非空缓存只能来自在该代际开始且通过原子发布检查的读。它支持旧回填隔离，却不检查语言内存模型、未知提交结果、代际回绕或分布式写入。这是核心证据，所以 importance=core；完整检查需要 detailed，但放在 L3，不阻挡宏观阅读。[s:s_invariant] [s:s_scope]

<a id="node-retry_cost"></a>

## 权衡：缩短锁持有时间，承担重复工作 [n:retry_cost]

状态锁不被慢 I/O 长期占用，但每次未命中需要两次进入锁、记录代际，冲突时还要重做存储读取。是否更快取决于写频率、存储延迟与锁竞争；本文没有测量答案。[s:s_cost]

<a id="node-short_sections"></a>

### 选择短临界区 [n:short_sections]

作者选择仅保护元数据操作，避免持锁跨越整个 I/O。它改变的是阻塞与重试之间的安排，不能直接写成“性能提升”。[s:s_cost]

<a id="node-io_constraint"></a>

### 选择由什么约束推动 [n:io_constraint]

S1 明确要求请求不能在等待存储期间一直持有状态锁。这限制了可选结构；不是由分析者代作者添加的目标。[s:s_scope]

<a id="node-delete_only"></a>

### 与删除基线的变化 [n:delete_only]

基线只删除现存副本，新协议还记录并撤销在途结果的资格。比较的是同一旧回填保证；没有用不同负载的性能数字制造优势。[s:s_race] [s:s_read]

<a id="node-progress_limit"></a>

### 安全性不代表进度保证 [n:progress_limit]

持续写入可能让读取一直重试；协议没有公平性、等待上界，也没有合并同代际的重复请求。阻止错误值与保证请求及时完成是两种不同结果。[s:s_cost]

<a id="node-validate_at_commit"></a>

## 可迁移部分：生效前复核前提 [n:validate_at_commit]

AI 从这份协议归纳出：工作可以先做，但结果对共享状态生效之前必须确认前提仍成立。适用于可检测变化、可原子提交、可安全丢弃结果的场景。如何迁移及何时失效见 [设计模式](design_patterns.md)。[s:s_read] [s:s_trace]

[返回主线](knowledge_spine.md) · [查看来源地图](document_map.md) · [返回总览](overview.md)
