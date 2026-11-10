---
name: architecture-first-reader
description: 从技术论文、博客、Markdown、PDF 与 PPT 中重建问题、核心 Idea、整体架构和设计决策的解释链，交付共享节点的知识主线与分层语义图谱。用于理解为什么这样设计、权衡与可迁移思想；默认宏观优先、细节按需，不代替逐页串讲或通用摘要。
---

# Architecture-First Reader

重建具有解释力的设计逻辑，让读者先理解材料为什么存在、核心 Idea 是什么、如何落实为结构，以及为什么这些设计可能有效。默认中文、一次分析一个主材料；用户指定的范围、基础、深度与语言优先。

最终交付八个文件：`overview.md`、`document_map.md`、`knowledge_spine.md`、`architecture_analysis.md`、`design_patterns.md`、`knowledge_nodes.json`、`knowledge_graph.json`、`knowledge_graph.mmd`。默认目录为工作区 `output/architecture-first-reader/<材料名>/`，已有产物使用新的目录，除非用户要求更新。

## 工作方式

先读 [执行流程](references/workflow.md)。以下七个阶段是推理过程，不要求把七份中间草稿另行交付。脚本只校验和转绘结构化内容；阅读、解释与设计模式抽象由 Agent 完成。

### 子代理编排

环境支持子代理时，主 Agent 在逐段精读前创建下列五个角色。创建角色不等于同时启动所有分析；主 Agent 按依赖顺序分派任务，只有所需输入就绪时才启动对应角色。环境不支持子代理时，由主 Agent 依序承担这些职责，不阻塞交付。

| 子代理 | 功能 | 交回主 Agent 的结果 |
| --- | --- | --- |
| `source-mapper` | 覆盖可访问正文、关键图表和附录，建立原文结构、阅读范围与来源定位，记录跨节衔接点和缺口。 | Document Map 草案、来源注册表草案、实际覆盖范围、各部分的论证作用及无法读取的位置。 |
| `architecture-analyst` | 基于 Document Map 精读相关原文，重建问题与动机、核心 Idea、整体架构、组件或证明依赖，并用具体输入走通机制。 | 动机链、核心 Idea、架构交互、关键设计候选、逐步机制说明，以及每一项的具体来源和不确定处。 |
| `evidence-critic` | 独立核对关键主张和设计链，检查证据适用范围、替代方案、收益与代价、归属和可迁移模式的边界。 | 已支持与未获支持的主张、证据错配或过度因果、推断标记、权衡与失效条件，以及对应来源。 |
| `learning-graph-editor` | 在主 Agent 完成综合并固定节点 ID 后，整理学习主线、L1/L2/L3 层级、语义关系和文件内导航，不另造事实。 | 使用既有节点与来源 ID 的 Spine/Graph 建议、分层理由、关系理由，以及主线或导航中的断点。 |
| `independent-reviewer` | 在完整草稿形成后，对照原始材料检查问题、Idea、架构、关键选择、证据、迁移边界及跨文件一致性。 | 按严重程度排序的问题清单、具体原文依据、缺失覆盖和需修正的节点或关系；不直接覆盖最终产物。 |

长材料可额外创建多个 `section-reader`。每个只负责明确且不重复的章节或页区间，交回该范围的“位置、主张、机制、证据、限制、待衔接问题”；不得各自生成全篇主线或知识图。

编排遵守以下规则：

1. `source-mapper` 先交回来源地图；`architecture-analyst` 与 `evidence-critic` 可在地图就绪后并行；`learning-graph-editor` 等待主 Agent 完成跨节综合；`independent-reviewer` 在结构校验后复核最终草稿。
2. 分派时提供主材料路径或 URL、版本、来源定位规则、具体章节或页区间和待解问题，不把整个任务原样转交，也不让子代理猜测上游结论。
3. 子代理只返回分析，不直接写入八个最终文件，不另建一套节点或来源 ID。所有关键发现必须附具体来源、归属和不确定处。
4. 主 Agent 负责核对关键原文、跨节衔接、冲突裁决、统一 ID 和最终写入。子代理输出不能直接当作全篇覆盖或事实正确性的保证。

### 七个分析阶段

1. **Global Understanding — 先覆盖材料。** 按 [材料适配](references/reading-strategies.md) 选择当前可用的读取工具，浏览全部可访问正文、关键图表和附录，记录标题、论证路径与缺口，建立 Document Map。长文可按节委派阅读，综合前核对覆盖和跨节联系。无法读取的部分具体标出，不能把仅阅读摘要或抽取文本称为完整分析。
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
- 用户随后追问时，先读取已有 JSON、对应原文和相关段落，再更新受影响节点与关系，保留未变化 ID，重新校验；不要每次生成另一套不兼容知识图。

## 校验、图谱与交付

正式结构：

- [Knowledge Nodes JSON Schema](schemas/knowledge-nodes.schema.json)
- [Knowledge Graph JSON Schema](schemas/knowledge-graph.schema.json)

两个 Schema 分别定义节点和边的正式结构；跨文件引用与语义不变量由校验器补充检查。JSON 不包含分析模板占位符。

在写完两个 JSON 和五个 Markdown 文件后，用本机 Python 3.10+ 执行，无需安装分析框架或模型 SDK：

```text
python3 <skill-dir>/scripts/render_mermaid.py <output-dir> --output <output-dir>/knowledge_graph.mmd
python3 <skill-dir>/scripts/validate.py <output-dir>
```

图谱的方向、过滤与转义要求见 [Mermaid 规范](references/mermaid.md)。可按需生成 L2/L3 或节点邻居图；默认交付仍为 L1，不把新推断塞进绘图脚本。

修复结构错误，再按 [质量评审](references/quality-review.md) 对照原文检查核心 Idea、架构交互、决策理由、证据作用和迁移边界。机器校验通过不代表教学正确或材料已完整读完。部分材料无法读取时仍交付可分析范围，显著说明缺口，不宣称达到完整验收。

交付时链接 `overview.md` 与输出目录，简述核心发现和影响理解的限制。无需默认制作网页、安装工具链、发布线上或展开所有公式。按需深入由 Markdown 导航、分层图谱及后续节点追问共同完成。

## 参考示例

需要学习输出粒度时，查看 [缓存协议材料](examples/versioned-cache/source.md) 与 [预期总览](examples/versioned-cache/expected/overview.md)。理论/算法材料另有 [可合并摘要说明](examples/mergeable-summary/source.md) 与 [独立试用产物](examples/mergeable-summary/expected/overview.md)，演示以不变量和证明依赖解释结构。两份均明确标注为原创合成材料，演示来源定位、设计推理、证据限制和模式边界，不作为真实系统性能依据。
