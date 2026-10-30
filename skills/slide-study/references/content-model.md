# Content contract (version 1)

The preprocessor writes `source.json`; the agent writes `lesson.json`. Keep teaching reasoning in the agent; scripts extract, validate and render, never generate explanations from keywords. All page references are **1-based physical positions in the original file**. Printed labels are separate and may be null.

## Source manifest

```json
{
  "schema_version": 1,
  "source": {"filename": "deck.pdf", "format": "pdf", "sha256": "...", "page_count": 2, "title": "..."},
  "warnings": [],
  "pages": [
    {"page": 1, "printed_page": null, "text": "extracted text", "notes": "", "image": "pages/page-0001.png", "width": 1440, "height": 810, "warnings": []}
  ]
}
```

One manifest entry and one readable image per source page. Image paths are relative to the manifest directory, and must stay inside it. The abbreviated example above omits page 2 for illustration only. Use actual presentation order and relationship targets for PPTX slide/notes mapping, never lexical XML filenames. Notes placeholders for date, footer, slide number and header are not teaching notes. `sha256` identifies the original input, including when a `.ppt` was converted. Rendered static slides do not capture all animation/video behavior; record these limitations.

## Lesson

```json
{
  "schema_version": 1,
  "title": "课程标题",
  "subtitle": "一句话课程问题",
  "source": {"filename": "deck.pdf", "sha256": "...", "page_count": 2},
  "overview": {
    "summary": "完整教学主线",
    "objectives": ["学完能够解释什么"],
    "prerequisites": ["所需基础"],
    "storyline": [{"title": "章节", "pages": [1, 2], "summary": "本章如何推进全篇"}]
  },
  "pages": [
    {
      "page": 1, "printed_page": null, "title": "页面标题", "section": "章节",
      "blocks": [{"kind": "source", "title": "核心内容", "text": "解释正文"}],
      "role": {"kind": "inference", "text": "为什么在这里讲这一页"},
      "bridge_prev": {"kind": "inference", "text": "怎样承接上一页；首页说明从这里开始"},
      "bridge_next": {"kind": "inference", "text": "怎样引出下一页；末页说明全课结束"},
      "takeaway": {"kind": "source", "text": "本页最应保留的理解"},
      "concept_ids": ["c1"]
    }
  ],
  "concepts": [
    {"id": "c1", "label": "概念", "description": "概念的简洁解释", "group": "主题", "pages": [1, 2], "kind": "source"},
    {"id": "c2", "label": "另一概念", "description": "另一概念的简洁解释", "group": "主题", "pages": [2], "kind": "source"}
  ],
  "relations": [
    {"id": "r1", "from": "c1", "to": "c2", "type": "prerequisite", "label": "理解前提", "explanation": "第 1 页建立的哪个内容如何帮助理解第 2 页", "pages": [1, 2], "kind": "inference"}
  ]
}
```

All source pages must appear exactly once and in original order. Page `printed_page` can be filled after visual inspection; do not infer a printed label from physical order. Empty `concept_ids` is valid for covers/section breaks. Every concept's `pages` and page `concept_ids` must be mutually consistent. A relation's evidence pages must include evidence from both endpoint concepts. All IDs must be unique within their collection, and every reference must resolve. Empty `relations` is valid if no defensible relationship exists.

`kind` is one of `source` (faithful paraphrase, including speaker notes), `supplement` (added background/example/derivation), `inference` (reconstructed teaching role/relationship), `uncertain` (specific unresolved source ambiguity). These labels describe provenance, not numerical confidence. Split a block if its provenance changes. Every role/transition/takeaway has its own label. Concepts and relationships carry the same labels.

Relationship types: `prerequisite`, `derivation`, `application`, `comparison`, `problem_solution`, `evidence`. Direction is from prerequisite to dependent idea, basis to result, method to application, problem to solution, or evidence to claim. `comparison` is symmetric and is rendered without an arrow. Explain the concrete connection; do not fabricate edges to make the graph connected.

Text is plain Unicode, with paragraph breaks, inline backticks, fenced code blocks, inline math `$...$` / `\(...\)`, and display math `$$...$$` / `\[...\]`. Do not embed HTML or rely on general Markdown parsing. Formula symbols need prose definitions. Unsupported math must remain visible and be flagged, not silently dropped. External citations may be plain HTTPS URLs in explanatory text. No HTML executes from course content.

## Commands

Run with the Python executable returned by `load_workspace_dependencies` (or one with pypdf/Pillow installed):

```text
python scripts/prepare_source.py INPUT --output PREPARED_DIRECTORY
python scripts/validate_lesson.py LESSON_JSON --source PREPARED_DIRECTORY/source.json
python scripts/build_site.py --source PREPARED_DIRECTORY/source.json --lesson LESSON_JSON --output OUTPUT_DIRECTORY
```

The builder produces `index.html`, `lesson.json`, `source.json`, `pages/`, local `assets/`, and a sibling `OUTPUT_DIRECTORY.zip`. It must reject incomplete coverage, mismatched source hashes/counts, invalid references, missing/unreadable images or missing bundled assets before reporting success. Course JSON is embedded safely in the HTML; the website uses no fetch, CDN or server. Keep canonical JSON files for later editing/rebuilding.

The builder also invokes `validate_math.cjs` with Node and the bundled KaTeX to reject unrenderable formulas before packaging. For a focused check use `node scripts/validate_math.cjs LESSON_JSON`. JSON/host-language backslashes must be escaped correctly: a literal `\bar` must not turn into a backspace character. Keep currency symbols outside math or escape literal dollar signs.
