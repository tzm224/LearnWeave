# 可合并的指数和摘要：把全局参考值的协调推迟到每次合并

每块保存“局部最大值＋相对该最大值的指数和”，合并时先对齐参考值再相加，就能用两标量摘要沿任意二叉树求得整体 log-sum-exp；任意树等价的保证限于精确实数算术。[n:insight] [s:rescaling]

**材料性质：** 这是用于评估阅读流程的原创合成技术说明，不是已发表论文，也没有实测实现。下述结论是对所给材料的阅读重建。[s:nature] [查看材料性质](document_map.md#source-nature)

阅读入口：[理解主线](knowledge_spine.md) · [架构与设计决策](architecture_analysis.md) · [可迁移思想](design_patterns.md) · [原文地图与来源](document_map.md) · [宏观知识图](knowledge_graph.mmd) · [节点数据](knowledge_nodes.json) · [关系数据](knowledge_graph.json)

## 为什么需要它

目标是计算 `log(sum(exp(x_i)))`。直接取指数可能溢出；统一减去全局最大值虽能避免正指数参数，但先找这个全局值需要协调所有块。本文要求已经分块的输入各自产出常数大小摘要，之后不保留原块也能合并。[n:problem] [s:setting] [s:contract] [查看约束](architecture_analysis.md#node-contract)

## 核心 Idea 如何变成架构

洞察是局部最大值不必从一开始就相同；只要记录参考值，后续就能转换。设计把它落实为“块内摘要 → 树内重标定合并 → 根部取对数”。例如 `[0]` 和 `[log(2)]` 分别输出 `(0,1)`、`(log(2),1)`；合并采用共同最大值 `log(2)`，得到 `s=1/2+1=1.5`，根部输出 `log(2)+log(1.5)=log(3)`。根部结果是沿原文例子的直接代数推演，非性能观测。[n:architecture] [s:merge] [s:rescaling]

深入：[整体结构与交互](architecture_analysis.md#node-architecture)。

## 为什么采用这些设计

两个局部 `s` 使用不同参考值，不能直接相加。以两块最大值中的较大者作为共同参考值，既能准确换算两项，也使重标定指数非正。每次合并保持“最大值正确，乘回参考因子后仍代表原指数和”这两个条件；树归纳由此成立。[n:rescale] [s:proof] [s:rescaling]

深入：[关键设计及替代方案](architecture_analysis.md#node-rescale)。

## 得到了什么，边界在哪里

理论证明支持精确实数模型中的正确性与结合性。每块输出两个标量，每次合并只需有界运算，但这不构成相较协调两遍方案的速度或精度比较。摘要也不能直接恢复每个 softmax 概率。浮点可能下溢、舍入，不同树形不保证逐位一致；NaN、无穷和空块被排除，空块单位元与误差界均未给出。[n:real_result] [n:tradeoff] [n:fp_limits] [s:proof] [s:costs] [s:limits] [查看证据与边界](architecture_analysis.md#node-proof)

## 值得迁移的思想

分析者可从中抽象“保存参考值与相对量，在合并处对齐参考值，用不变量证明摘要闭合”。新场景必须有正确的转换规则和闭合摘要；不能顺带继承浮点一致性或性能保证。这是 AI 推断。[n:pattern] [s:representation] [s:proof] [查看迁移条件](design_patterns.md#node-pattern)

## 阅读范围

已读原文件第 1–31 行：标题、材料性质、四节正文与所有公式。原件无图片、附件或附录，未发现读取缺口。完整覆盖只针对这份合成说明。[原文地图](document_map.md)
