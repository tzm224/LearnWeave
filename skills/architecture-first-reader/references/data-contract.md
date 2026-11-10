# 数据契约 v1.0

正式结构见 `../schemas/knowledge-nodes.schema.json`、`../schemas/knowledge-graph.schema.json`；本文件解释字段语义。两个 JSON 是唯一结构化事实源，Markdown 和 Mermaid 是它们的可读投影。修改节点后重新生成 Mermaid，并同步主线和正文引用。

## knowledge_nodes.json

顶层包含 `schema_version: "1.0"`、`document`、`source_refs`、`nodes`。

`document` 包含 `id`、`title`、`source_type`（`paper|blog|markdown|pdf|pptx|ppt`）、`uri` 和 `coverage`。`uri` 是原件路径或 URL，禁止把暂存路径冒充来源。

`coverage` 包含 `status`（`complete|partial`）、`inspected_units`（实际检查过的页、节或行区间字符串列表）、`gaps`（`{location, reason, impact}` 对象列表）。`complete` 必须没有缺口；出现无法读取的图、附录或页面时用 `partial`。文本读取不等于图表已经检查。机器只能检查声明一致性，不能证明实际读完了材料。

`source_refs` 是来源位置注册表。每项包含 `id`、`origin`（`primary|external`）、`uri`、`kind`（`page|slide|lines|section|figure|table|equation|url_fragment`）、`locator`，可选 `note`。位置要足够精确以重查，例如 `physical page 4, Figure 2`、`lines 32–46`、`section 3.2, paragraph 2`。PDF/PPT 使用 1 起始物理页号；印刷页号可写在 note。外部补充保留独立 URI，不能伪装成主材料内容。

每个节点包含：

- `id`：匹配 `[a-z][a-z0-9_-]*`，跨所有输出保持稳定。
- `type`：`problem|constraint|insight|architecture|design_decision|component|mechanism|tradeoff|evidence|concept|pattern|outcome`。额外的 `architecture` 表示整体结构，以免把组件列表冒充架构。
- `title`、`summary`：名称与一段可独立理解的解释。
- `importance`：`core|supporting|peripheral`，表示对这份材料的解释力。
- `learning_depth`：`orientation|working|detailed`，表示建议读者掌握到何种程度；与重要性、展示层级分别判断。
- `level`：`L1|L2|L3`，默认在哪一层首次呈现。核心公式仍可在 L3；重要设计也可以只需 orientation。
- `source_refs`：非空来源 ID 列表。推断引用其依据，不能用引用消除推断身份。
- `attribution`：`author_claim|direct_evidence|ai_inference|external_background`。
- `confidence`：`{level: "high|medium|low", rationale: "具体理由"}`，描述提取或推断的把握，不表示作者结论正确的概率。
- 可选 `details`：按类型补充的对象。`evidence` 必须含 `evidence_kind`（`empirical|theoretical|worked_example|observation`）、`scope`、`result`、`limitations`（字符串列表）；其他类型可使用 `assumptions`、`interfaces`、`alternatives` 等字段。

同一节点不要混写作者事实与分析者推断；必要时拆成两个节点。可迁移 `pattern` 通常属于 `ai_inference`，需在 details 中记录 `applicability` 和 `failure_modes`（均为非空字符串列表），即使该模式由作者明确提出也保留适用边界。

## knowledge_graph.json

顶层包含 `schema_version: "1.0"`、`document_id`、`nodes_file: "knowledge_nodes.json"`、`spine`、`views`、`edges`。

`spine` 是 `{node_id, why_next}` 的有序数组，引用现有节点，至少一项，不重复节点。首项解释为何从这里开始，其后解释承接的具体问题；不要求覆盖所有节点，也不等同于章节顺序。

`views` 包含三个非空 ID 列表：`L1` 恰好包含 level=L1 的节点；`L2` 包含 L1 与 L2；`L3` 包含全部节点。这是逐层展开，节点本身不复制。L1 建议 5–15 个节点，材料简单时允许更少；过多时重组宏观视图，不能删证据。默认 Mermaid 只绘 L1；可生成 L2/L3 或以某节点为中心的邻居图。

每条边包含 `id`、`source_id`、`target_id`、`relation`、`rationale`、非空 `evidence_refs`、`attribution`、`confidence`。归属与可信度规则同节点。允许 `edges: []`，不能造边补齐画面。关系方向固定如下：

- `motivates`：问题/约束 → 洞察/设计，解释动机。
- `addresses`：设计/机制 → 试图解决的问题/约束；不代表已经解决。
- `implements`：架构/设计/机制 → 被落实的 Idea。
- `depends_on`：依赖方 → 前提。
- `enables`：机制/设计 → 得以实现的能力或结果。
- `part_of`：组成部分 → 整体；不允许包含环。
- `supports`：证据节点 → 受支持的主张；rationale 写清支持范围，不能拿汇总实验证明每个模块的独立作用。
- `contrasts_with`：对称关系，Mermaid 不画箭头；交换端点也视为同一关系。
- `generalizes_to`：具体设计/机制 → pattern 节点。
- `trades_off`：设计 → tradeoff 节点；权衡节点同时写出获得与付出。

关系需要自己的证据和归属，不能直接继承端点的作者归属。除 `supports` 起点必须是 evidence、`generalizes_to` 终点必须是 pattern、`trades_off` 终点必须是 tradeoff 外，不以僵硬的类型矩阵限制真实材料。所有来源 ID 和节点 ID 必须解析成功；无自环或重复语义边。

## 可读输出与定位

八个交付文件：`overview.md`、`document_map.md`、`knowledge_spine.md`、`architecture_analysis.md`、`design_patterns.md`、`knowledge_nodes.json`、`knowledge_graph.json`、`knowledge_graph.mmd`。

Markdown 用 `[n:node_id]` 标记节点，用 `[s:source_id]` 标记来源；自动校验检查这些标记是否存在于 JSON。主线文件按 spine 顺序写节点；各主线步骤使用 `## 1. 标题 [n:node_id]` 格式，正文可引用其他节点。document_map 中为来源 ID 提供可点击的原件/URL 链接及具体位置。overview 链接到其余文件，architecture_analysis 使用 `## 标题 [n:node_id]` 作为按需深入的定位点。必要的背景节点可以来自 external 来源；一个文件默认分析一个主材料，外部核对不改变这个范围。

缺失证据、未报告的替代方案或尚未验证的权衡写成正文中的明确限制，不制造 evidence 节点填空。已有方案若材料未提及，写“原文未讨论”；分析者提出的替代设计必须标明推断并说明比较条件。
