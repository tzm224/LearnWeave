---
name: architecture-first-reader
description: 从技术论文、博客、Markdown、PDF 与 PPT 中重建问题、核心 Idea、整体架构和设计决策的解释链，生成单个离线 HTML，沿知识主线阅读、展开设计与证据、探索分层图谱。用于理解为什么这样设计、权衡与可迁移思想；默认宏观优先、细节按需，不代替逐页串讲或通用摘要。
---

# Architecture-First Reader

重建具有解释力的设计逻辑，让读者先理解材料为什么存在、核心 Idea 是什么、如何落实为结构，以及为什么这些设计可能有效。默认中文、一次分析一个主材料；用户指定的范围、基础、深度与语言优先。

每份材料交付一个可独立打开的 `output/architecture-first-reader/<材料名>/index.html`。首页先读总览，再沿主线连续阅读；节点讲解、证据定位、L1/L2/L3 图谱和可恢复的分析稿件都保存在同一文件。首次分析使用独立的工作目录和交付目录，已有产物使用新目录，除非用户要求更新。

## 工作方式

默认由一个 agent 完成全篇分析。通览后，若方法、实验或附录各自有可独立回答并定位证据的问题，可委派 subagent 分块阅读。前后紧密相依的证明由同一 agent 连贯阅读，即使篇幅很长。若关键结论依赖跨章推理，或容易误判证据的支持范围，可在形成初稿后单独委派复核，包括由一个 agent 完成阅读的情况。职责与交接见[执行流程中的分工说明](references/workflow.md#subagent-分工与交接)。

先读[执行流程](references/workflow.md)，再按以下七个阶段分析材料。Agent 负责解释与设计模式抽象，脚本负责校验和构建网页。

1. **Global Understanding — 先覆盖材料。** 按 [材料适配](references/reading-strategies.md) 选择当前可用的读取工具，浏览全部可访问正文、关键图表和附录，记录标题、论证路径与缺口，建立 Document Map。综合前核对覆盖和跨节联系。无法读取的部分具体标出，不能把仅阅读摘要或抽取文本称为完整分析。
2. **Problem & Motivation — 还原动机链。** 从材料中区分问题、已有方案、已有方案的局限、约束及目标。区分“作者认为需要改善”与“证据已经证明存在问题”。原文未讨论的基线或约束明确记为未报告。
3. **Core Idea & Architecture — 从洞察到结构。** 先用一句话解释改变了什么思路，再描述整体结构、模块职责、接口与信息/控制流。用一个具体输入走过系统或算法，指出状态怎样变化、约束在哪里生效。理论材料使用假设、关键构造、引理依赖和证明路径；不能硬套工程模块。
4. **Design Reasoning & Abstraction — 解释选择。** 对核心决策重建 `Problem → Constraint → Insight → Design Decision → Mechanism → Outcome / Trade-off`。链中缺乏证据的环节标明缺口，不能补造因果。对照作者讨论过的替代方案；分析者另提的方案明确标为推断。分开写设计的预期收益、材料观察到的结果和尚未验证的解释。提炼可迁移模式时同时给出适用条件与失效情境，允许没有可靠模式。
5. **Knowledge Structuring — 先主线，后节点。** 用理解依赖组织 Knowledge Spine，允许重排原章序。只提取解释主线必需或有迁移价值的节点。按 [数据契约](references/data-contract.md) 分别判断 `importance`、`learning_depth`、`level`；知识重要性不等于公式复杂度，也不等于需要深入的程度。
6. **Architecture Knowledge Graph — 组织语义关系。** Spine 与 Graph 引用同一批节点 ID。为关系写出方向、理由、证据、来源归属与可信度。支持 L1 宏观、L2 设计机制、L3 细节的累积视图，默认 L1 约 5–15 个节点；材料简单时可更少。孤立节点和空边集有效，不为了连通性造边。写出符合正式 Schema 的两个 JSON。
7. **Explanation & Navigation — 生成可读产物。** 依次讲解一句话理解、问题和动机、核心 Idea、架构、关键决策、有效机制、证据与权衡、可迁移思想。使用 [输出模板](assets/templates/overview.md) 及同目录其余四个模板，填充而非复述提示语；模板不是必须填满的算法框架。正文用稳定节点/来源标记及文件内链接连接主线、深入分析和原文位置。

## 证据与学习深度

- 重要节点和每条关系都指向具体原文位置。分别标注 `author_claim`、`direct_evidence`、`ai_inference`、`external_background`；推断即使有引用也仍是推断。
- `confidence` 表示提取或推断的把握，不是作者结论正确的概率。无法确认的动机写成可能解释，不能代作者讲述思考过程。
- 实验只支持其条件下的结论；整体结果不能自动证明某模块的独立贡献。收益与代价写清比较对象、约束、实验范围与缺失的消融。
- L1 回答问题、Idea、结构和结论；L2 解释决策、依赖和机制；L3 收纳公式、算法步骤、实验与实现。默认不展开所有微观教学；用户追问节点时沿现有 ID 深入，必要时交给环境中可用的 Teach Skill，并传递背景、前置、来源与待解问题。没有 Teach Skill 也能针对该节点解释，不阻塞当前交付。
- 用户随后追问时，从已有工作稿或 HTML 恢复稿件，重读相关原文，修改受影响的正文、节点与关系，保留未变化 ID，再构建 HTML。

## 构建与继续编辑

在工作目录编写五份完整 Markdown 及 [节点 JSON](schemas/knowledge-nodes.schema.json) 和 [关系 JSON](schemas/knowledge-graph.schema.json)。正文承载走读、证明、反例与迁移条件；使用模板中的节点标记、来源标记和锚点，把深入讲解关联到具体主线步骤。原文地图为每条来源写明证据支持了什么、具体定位及原件链接。优先写可从稿件目录解析的相对链接，或稳定的原始 URL。

用 Python 3.10+ 构建并检查成品。技能自带网页资源及解析器，构建器也接受旧版八文件目录。

```bash
python3 <skill-dir>/scripts/build_reader.py build <稿件目录> --output <交付目录>
python3 <skill-dir>/scripts/validate.py <交付目录>/index.html
```

完成 [内容与离线验收](references/quality-review.md) 后，交付 `index.html` 的链接，说明核心发现及实际影响阅读的缺口。页内证据说明、定位和图谱随文件保存，打开原件需要对应路径或网址可访问。

后续只有 HTML 时，先将内嵌稿件恢复到独立工作目录，再按上面的命令构建。修订后的分析继续沿用原节点 ID。

```bash
python3 <skill-dir>/scripts/build_reader.py extract <已有的index.html> --output <稿件目录>
```

HTML 单独移动后，原先的相对路径可能失效。若原件仍可访问，重建时用 `--source-base <原稿件的链接基准目录>` 重新定位相对原件链接。

## 参考示例

[缓存协议阅读页](examples/versioned-cache/reader/index.html) 可对照 [缓存原文](examples/versioned-cache/source.md) 检查一次竞态中的状态变化。[指数和摘要阅读页](examples/mergeable-summary/reader/index.html) 可对照 [算法原文](examples/mergeable-summary/source.md) 检查不变量、证明与浮点适用边界。两份均为原创合成材料。
