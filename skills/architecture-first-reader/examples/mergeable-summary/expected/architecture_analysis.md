# 可合并指数和摘要：架构与设计推理

本文描述算法与证明，不描述一个已实现的硬件或分布式系统。Insight 是“参考值可在之后转换”；Idea 是“先产生局部摘要，合并时对齐参考值”；Design 才是具体的两标量表示、合并公式与根部输出。以下按稳定节点链接展开，来源均为合成说明。[s:nature]

<a id="node-problem"></a>

## 先确定计算问题 [n:problem]

需要计算非空有限实数序列的 `log(sum(exp(x_i)))`。直接计算 `exp(x_i)` 可能溢出；全局最大值移位把指数参数变为非正，但在计算全局移位和前要协调各块找出这个值。原文因此提出摘要的可合并目标；它没有证明现有协调方案在任何硬件上一定更慢。[s:setting] [s:contract] [查看来源](document_map.md#source-setting)

<a id="node-contract"></a>

## 摘要须满足什么契约 [n:contract]

输入已分为非空块，元素为有限实数。每块只输出常数大小摘要，后续合并不需要保留原始块；任意二叉树应在精确实数算术中给出相同结果。这里“合并元素”保留序列元素重数，不作去重集合运算。NaN、无穷及空块被排除，因此现有定义没有空块单位元。[s:contract] [s:limits]

“无需保留原块”描述摘要之后的合并接口；原文没有限定块内生成摘要的遍历次数或缓存实现，也没有声称完整计算只扫描每个输入一次。[查看来源](document_map.md#source-contract)

<a id="node-insight"></a>

## 参考值不是不可改变的全局前置条件 [n:insight]

局部 `s` 的数值以局部最大值为参考。把这个参考值 `m` 一同保留，就能在未来知道另一个块的最大值时换算，而不必回看原块。原文明确指出局部摘要不需要最终全局最大值；共同参考值在每次合并时更新。[s:representation] [s:rescaling] [查看来源](document_map.md#source-rescaling)

<a id="node-architecture"></a>

## 摘要、合并、解码的完整路径 [n:architecture]

**输入与输出：** 输入是上述非空分块；最终输出是一个整体 log-sum-exp 标量。架构中只有算法阶段、状态接口与证明义务，没有虚构线程、网络协议或 GPU 内核。

**执行路径：** 块内先形成 `(m_A,s_A)`；每个内部节点接收两个摘要，更新共同最大值并重标定局部和，输出相同形状的 `(m,s)`；根节点只在最后求 `m+log(s)`。原始元素在合并接口中不再需要。[s:representation] [s:merge]

沿原文的两个单元素块走一遍：

1. `[0]` 输出 `(0,1)`，`[log(2)]` 输出 `(log(2),1)`。
2. 合并最大值变为 `m=log(2)`；第一项换到新参考值，贡献从 `1` 变为 `1/2`，第二项保持 `1`。
3. 输出摘要 `(log(2),1.5)`。继续合并时传递的仍是这两个标量。
4. 若此处是根，则输出 `log(2)+log(1.5)=log(3)`。这一步是依据原文公式所作的直接代数推演。

**接口与证明义务：** `summarize` 建立规范摘要；`merge` 接受两个规范摘要并保持规范性；`finish` 把根摘要变为对数结果。层数或树形不改变实数证明，因为每个内部节点执行同一个保持不变量的变换。[s:proof] [s:rescaling] [查看来源](document_map.md#source-merge)

<a id="node-summary"></a>

## 为什么携带两个标量 [n:summary]

定义 `m_A=max(A)`，`s_A=sum(exp(x_i-m_A))`。其含义是 `exp(m_A)*s_A` 表示该块的原指数和。参考值说明相对量的尺度，`s_A` 保存该尺度下的聚合值。实现无需真正构造 `exp(m_A)*s_A`，因为那个乘积本身可能溢出；它首先是证明表示正确性的数学量。[s:representation] [查看来源](document_map.md#source-representation)

原文明确给出这两个量，没有提供“两个标量是所有方案的最小信息量”之类的下界证明，也没有排除所有其他表示。

<a id="node-rescale"></a>

## 关键选择：用共同最大值重标定 [n:rescale]

**Problem → Constraint：** 分块需要独立产出摘要，后续只能利用摘要；然而两个局部 `s` 的参考值未必相同。[n:problem] [n:contract] [s:contract] [s:representation]

**Insight → Design Decision：** 既然参考值已保留，就先对齐再相加。选择 `m=max(m_A,m_B)`，计算：

```text
s = s_A * exp(m_A-m) + s_B * exp(m_B-m)
```

**Mechanism：** 两个参考值差均非正，因此重标定指数不产生正参数；乘回 `exp(m)` 时两项各自恢复原来的 `exp(m_A)*s_A` 和 `exp(m_B)*s_B`。关键收益来自换算保留了含义，而不是局部 `s` 本来可直接相加。[n:invariant] [s:merge] [s:proof] [s:rescaling]

**Outcome / Trade-off：** 得到同形摘要和实数模型中的正确合并，每次需执行有界的标量和指数运算。具体运行时间、误差与硬件性能仍未验证。[s:costs] [s:limits]

**作者讨论的替代方案：** 先协调全局最大值、再求全局移位和能完成同一计算目标，但需要先获得全局参考值；原文没有速度对比。选最大值却直接相加两个 `s` 则是错误规则，被下面的反例否定。没有其他已报告替代方案或消融实验。

**仍然未知：** 原文未测量不同树形的性能或精度，也未比较所有可选参考值。不能把采用最大值的理由扩张为“最大值在全部实现中最优”。[查看来源](document_map.md#source-rescaling)

<a id="node-invariant"></a>

## 保持规范摘要的机制 [n:invariant]

正确摘要同时满足两个条件：`m` 是所汇集元素的最大值，`exp(m)*s` 是这些元素的指数和。仅保存总和相等却忽略最大值条件，不足以完成这里“输出就是规范摘要”的证明。合并公式保证这两个条件同时保持；下一层因此可以直接使用同一规则。[s:proof] [查看来源](document_map.md#source-proof)

<a id="node-real_result"></a>

## 任意树结果相同究竟指什么 [n:real_result]

叶子建立规范摘要，每个内部节点保持规范摘要，因此根就是全体元素的规范摘要；取 `m+log(s)` 得到目标值。改变括号或树形不改变精确实数中的规范摘要，于是得到该模型下的结合性。它不含浮点逐位一致的承诺，也没有给空块定义单位元；不能直接将材料描述为已经完整规定了含空输入的代数结构。[s:proof] [s:limits] [查看来源](document_map.md#source-proof)

<a id="node-proof"></a>

## L3：代数证明与树归纳 [n:proof]

这是理论证据，支持实数恒等式与规范摘要保持，不支持速度、浮点误差界或不同树形的位级一致性。[s:proof] [s:limits]

对两个正确摘要，定义 `m=max(m_A,m_B)` 与上面的 `s`：

```text
exp(m)*s
= exp(m)*s_A*exp(m_A-m) + exp(m)*s_B*exp(m_B-m)
= exp(m_A)*s_A + exp(m_B)*s_B
= sum over A of exp(x_i) + sum over B of exp(x_i).
```

同时 `m` 是两块合并后的最大值，所以合并结果就是整体的规范对 `(m,s)`。对非空块，`s>0`，最终 `m+log(s)=log(exp(m)*s)`。对树作归纳即可扩展至全体块；重复值照其出现次数参与求和。[查看来源](document_map.md#source-proof)

<a id="node-counterexample"></a>

## L3：反例定位错误机制 [n:counterexample]

`[0]` 和 `[log(2)]` 的局部 `s` 都是 `1`，但其单位不同。取共同参考值 `log(2)` 后，正确摘要是 `(log(2),1.5)`；直接相加会得到 `(log(2),2)`，表示的总和为 `4` 而不是 `3`。最后一项总和对比是对原文例子的直接推演。[s:rescaling]

该反例足以否定“直接加局部 s”的普遍规则；它独自不能证明正确公式适用于所有输入，一般性来自上面的代数证明。[查看来源](document_map.md#source-rescaling)

<a id="node-tradeoff"></a>

## 可归约摘要的收益与信息边界 [n:tradeoff]

每块两个标量，每次合并只需有界数量的标量运算和指数运算。它允许块内计算后再作树归约，并且合并阶段不必访问原输入。这是结构与运算形态的结论。[s:costs]

代价包括合并时的重标定运算，以及摘要不能直接恢复逐项值：若要每个 softmax 概率，仍需保留或重访输入。原文没有测 GPU 内核，也没有证明相较协调两遍实现更快。总体复杂度形态不能代替具体性能测量。[查看来源](document_map.md#source-costs)

<a id="node-fp_limits"></a>

## 浮点与输入范围的边界 [n:fp_limits]

非正的重标定指数避免了这一步因正参数过大而指数溢出的风险，仍可能让很小的贡献下溢。舍入会破坏精确结合性，所以平衡树和顺序折叠可能不同。材料未建立误差界，也未证明哪种实现更准确。[s:limits]

输入范围排除 NaN、无穷和空块；没有空块单位元。因此实现若要支持这些情况，需要另行规定语义与规则。以上是原文明确的边界，不是当前阅读漏掉的附录。[查看来源](document_map.md#source-limits)

<a id="node-pattern"></a>

## 从机制走向可迁移结构 [n:pattern]

AI 分析可抽象出“参考值＋相对量 → 合并时对齐 → 规范摘要保持”的模式；迁移必须检查转换规则与闭合性。它不自动产生新场景的数值或性能保证。[s:representation] [s:merge] [s:proof] [展开条件与失效边界](design_patterns.md#node-pattern)

[回到理解主线](knowledge_spine.md) · [来源地图](document_map.md) · [返回总览](overview.md)
