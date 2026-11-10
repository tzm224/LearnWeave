<p align="center">
  <img src="assets/learnweave-logo.png" alt="LearnWeave logo" width="840">
</p>

# LearnWeave · From Material to Understanding

[中文](README.zh.md) | **English**

**LearnWeave turns knowledge materials into systems people can understand and learn.** It transforms slide decks, papers, and technical articles into guided explanations, learning paths, and traceable knowledge structures.

This repository contains two skills that can be installed separately:

- [slide-study](skills/slide-study/SKILL.md): explains a deck in its original page order and builds an offline study website.
- [architecture-first-reader](skills/architecture-first-reader/SKILL.md): reconstructs core ideas, architecture, and design reasoning from papers, technical articles, and slides, delivering a shared knowledge spine and layered graph as Markdown, JSON, and Mermaid.

**Original version:** [Download slide-study v1.0.0 ZIP](https://github.com/tzm224/LearnWeave/archive/refs/tags/v1.0.0.zip), tagged `v1.0.0` at commit `be044cc`. Extract and use `skills/slide-study/`. The link continues to refer to that release's snapshot. This addition preserves the existing `skills/slide-study/` files.

## architecture-first-reader quick start

Clone this repository and run the following from its root to install the new skill. An existing installation is preserved so you can choose how to update it:

```bash
git clone https://github.com/tzm224/LearnWeave.git
cd LearnWeave

skill_install_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skill_install_dir"
if [ -e "$skill_install_dir/architecture-first-reader" ]; then
  printf '%s\n' 'architecture-first-reader already exists; back up or move the old version before installing.'
else
  cp -R skills/architecture-first-reader "$skill_install_dir/architecture-first-reader"
fi
```

Then ask:

```text
Use $architecture-first-reader to analyze this material in English.
Explain the problem, core idea, architecture, and key design decisions, then the evidence,
trade-offs, and transferable ideas. Start with the big picture and provide a knowledge
spine and L1/L2/L3 graph, with details available as needed.
```

See the [system design example](skills/architecture-first-reader/examples/versioned-cache/expected/overview.md) and [theory/algorithm example](skills/architecture-first-reader/examples/mergeable-summary/expected/overview.md). Both are explicitly labeled synthetic materials. The new skill includes 22 automated tests; it has not yet completed acceptance testing on a real paper or visual rendering checks in a Mermaid viewer. Its validation and graph generation tools require only the Python 3.10+ standard library; source reading uses the agent's available tools.

The functionality, installation, and usage of `slide-study` follow below.

Turn a slide deck into an offline study website you can explore page by page or concept by concept.

`slide-study` is a Codex skill. It first reads the entire deck, then explains each page in its original order: what it teaches, why it appears at that point, and how it connects to the surrounding material. It also builds a knowledge graph with source pages and explanations for every relationship. It is designed for readers who know the subject's foundations but are studying this course for the first time.

## What it does

- **Guided notes for every page**: Start with a course overview and reading path, then explain mechanisms, examples, derivations, and takeaways. Keep cover pages brief, expand key ideas, and identify what changes across progressive slides.
- **Evidence-backed knowledge graph**: Merge synonymous concepts and connect prerequisites, derivations, applications, comparisons, problems and solutions, and supporting evidence. Every relationship includes a reason and links back to source pages.
- **Visible provenance**: Distinguish source material (`source`), supplementary explanations (`supplement`), reconstructed reasoning (`inference`), and unresolved content (`uncertain`).
- **Slides alongside explanations**: Use a side-by-side desktop layout and a stacked narrow-screen layout, with image zoom, search, a table of contents, page jumps, and previous/next navigation.
- **Interactive exploration**: Zoom, pan, search, and highlight neighboring concepts in the graph; navigate both ways between notes, concepts, and source pages.
- **A complete deliverable**: Cover the entire deck in one delivery, preserve the original file, and produce a standalone website folder, a ZIP archive, and editable course data.

## Inputs and outputs

Supports **PPTX and lecture PDF files**, plus legacy **PPT files** converted locally with LibreOffice. Each run handles one deck. PPTX pages and speaker notes are matched using the actual presentation order.

The generated folder contains:

```text
my-course/
├── index.html       # Study entry point
├── lesson.json      # Editable notes, concepts, and relationships
├── source.json      # Original page information and provenance
├── pages/           # Original page images
└── assets/          # Local scripts, styles, and math fonts
my-course.zip
```

Extract the ZIP and open `index.html` to study. The finished website needs no account, server, model API, or CDN; course data is embedded directly in the page. Creating a course requires an AI agent to read the deck, write the notes, and review the content. The scripts handle extraction, rendering, validation, and packaging.

**This README is available in Chinese and English. The study website's interface is currently Chinese, and explanations default to Chinese.** You can request another language for the explanations; the website has no interface language switch.

## Installation

Clone the repository and copy the complete skill folder into your local skills directory. These commands will not overwrite an existing `slide-study` installation:

```bash
git clone https://github.com/tzm224/LearnWeave.git
cd LearnWeave

skill_install_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skill_install_dir"
if [ -e "$skill_install_dir/slide-study" ]; then
  printf '%s\n' 'slide-study already exists; back up or move the old version before installing.'
else
  cp -R skills/slide-study "$skill_install_dir/slide-study"
fi
```

The default location is `~/.codex/skills/slide-study`. If `CODEX_HOME` is set, the destination is its `skills/slide-study` subdirectory. Prepare the dependencies using the [environment guide](skills/slide-study/references/setup.md), then invoke the skill in a Codex environment that supports skills.

## Usage

Provide your deck to Codex and name the skill, for example:

```text
Use $slide-study to process this lecture.pdf.
Read the entire deck first, then explain every page in its original order:
its content, its role, and its connections to the preceding and following pages.
Add the background, examples, and derivations needed to understand it.
Build a knowledge graph with source-page references, and deliver the complete
offline study website and ZIP in one go. Write the explanations in English.
```

You can also specify your background, chapters to emphasize, explanation language, or output location. Long decks are processed internally by chapter, then reconciled for consistent terminology, transitions, and cross-chapter relationships.

## Generation environment

| Purpose | Dependencies |
| --- | --- |
| Python scripts | Python 3.10+, `pypdf`, and `Pillow`; versions are listed in [requirements.txt](skills/slide-study/requirements.txt) |
| PDF page rendering | Poppler's `pdftoppm` |
| Formula validation and website packaging | Node.js; uses the bundled KaTeX files, with no `npm install` needed |
| PPTX rendering | An installed Codex Presentations renderer, or LibreOffice `soffice` + Poppler as a fallback |
| Legacy PPT conversion | LibreOffice `soffice` |
| Reading the finished website | A modern browser; none of the generation tools above are needed |

See the [environment guide](skills/slide-study/references/setup.md) for dependency installation, executable paths, and script commands.

## Quality and limitations

Scripts validate page coverage, image assets, reciprocal concept references, source information, and formulas. Teaching explanations, derivations, and relationship evidence still need review against the original pages. Scanned PDFs require visual reading. Static pages cannot preserve full animation or video behavior, and converters may substitute fonts or change layouts. Unreadable content should be identified by its specific page number.

Development checks used real 47-page and 134-page decks, plus a PPTX fixture with reordered slides, hidden slides, and speaker notes. The package also includes 17 automated tests. Browser interactions were checked through a local HTTP preview, but the browser tool prohibited `file://` at the time, so opening the website directly from disk and with the network disconnected was not tested. Future generation tasks should verify this in a permitted environment and report any checks they could not complete.

## Repository layout

```text
skills/slide-study/
├── SKILL.md          # Skill entry point and workflow
├── agents/           # Codex interface metadata
├── references/       # Teaching standards, content contract, and setup
├── scripts/          # Preprocessing, validation, building, and tests
├── assets/           # Website template and local KaTeX resources
└── requirements.txt
```

- [Skill instructions](skills/slide-study/SKILL.md)
- [Teaching standards](skills/slide-study/references/teaching.md)
- [Content contract](skills/slide-study/references/content-model.md)

Math rendering uses the bundled **KaTeX 0.19.1**. Its third-party license is included in [KaTeX LICENSE](skills/slide-study/assets/vendor/katex/LICENSE), with source details in [provenance.json](skills/slide-study/assets/vendor/katex/provenance.json). That license applies to KaTeX and is not a license for the entire repository.
