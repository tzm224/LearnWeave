<p align="center">
  <img src="assets/learnweave-logo.png" alt="LearnWeave 标志" width="840">
</p>

# LearnWeave · 从知识材料到理解体系

**中文** | [English](README.md)

**LearnWeave 将知识材料转化为适合人学习与理解的体系。** 它把课件、论文和技术博客等材料，转化为有讲解、有学习主线、可回溯来源的知识结构。

本仓库包含两套可以分别安装的技能：

- [slide-study](skills/slide-study/SKILL.md)：按课件原页序串讲，生成离线学习网页。
- [architecture-first-reader](skills/architecture-first-reader/SKILL.md) 把一篇论文、技术博客或一份课件整理成单个离线 HTML，带你读懂作者为什么这样设计。

**第一版下载：** [slide-study v1.0.0 ZIP](https://github.com/tzm224/LearnWeave/archive/refs/tags/v1.0.0.zip) 对应 `v1.0.0` 标签和固定提交 `be044cc`；解压后取 `skills/slide-study/` 即可。

## 用 architecture-first-reader 读懂设计

读完一篇论文，你可能记住了方法的名字，却还讲不清作者为什么要多做这一步。把材料交给这个 skill，打开生成的 `index.html`，先看作者要解决什么问题，再沿着问题读懂关键设计、证据和代价。

写入新值后明明清空了缓存，为什么下一次请求还能读到旧值？顺着一次读写交错往下看，你会发现，较早开始的读取可能在删除之后才把旧值填回来。有了这个例子，再看“为什么比较版本和写回缓存必须在同一把锁里”，就知道这把锁防住的是哪种情况。

- **控制阅读深度。** 沿主线连续读，遇到关键一步可以原处展开反例、证明或实现细节。
- **查清结论的依据。** 点击“依据”查看原文位置和支持范围，分清作者的主张、直接证据和 AI 的推断。关闭后接着读。
- **沿概念探索。** 在图谱里搜索一个节点，从宏观图切到机制或细节，点一条关系看两个概念为什么相连，也可以跳回对应讲解。

可以先试读两份原创教学示例。在 GitHub 打开文件后，选择 **Download raw file**，再用浏览器打开下载的 HTML。

- [缓存协议示例](skills/architecture-first-reader/examples/versioned-cache/reader/index.html) 的第 5 步可以展开比较和回填之间的竞态。
- [可合并摘要示例](skills/architecture-first-reader/examples/mergeable-summary/reader/index.html) 从一次两块数据的合并讲到树形证明，再说明浮点舍入如何限制结论。

### 安装与使用

克隆仓库并复制完整的技能目录。以下命令会保留已有的同名安装。

```bash
git clone https://github.com/tzm224/LearnWeave.git
cd LearnWeave

skill_install_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skill_install_dir"
if [ -e "$skill_install_dir/architecture-first-reader" ]; then
  printf '%s\n' 'architecture-first-reader 已存在；请先备份或移走旧版本，再安装。'
else
  cp -R skills/architecture-first-reader "$skill_install_dir/architecture-first-reader"
fi
```

安装后，附上材料，就可以这样提问。

```text
用 $architecture-first-reader 带我读这篇论文。我想弄懂作者为什么这样设计。
先讲主线，用一个具体例子走过关键步骤，再让我点开看证据和适用条件。
```

成品位于 `output/architecture-first-reader/<材料名>/index.html`。单独保存或转发这个文件就能离线阅读。以后想继续追问，还可以从 HTML 恢复分析稿并沿用原有节点。查看原件需要对应文件或网址仍可访问。构建使用 Python 3.10+ 和技能自带资源。旧版目录转换和恢复命令见[技能说明](skills/architecture-first-reader/SKILL.md)。

以下介绍 `slide-study` 的功能、安装与使用。

把一份课件变成可以沿页学习、也可以沿概念探索的离线学习网页。

`slide-study` 是一个 Codex skill。它先理解全篇，再按原页序解释“讲了什么、为什么在这里讲、如何承接前后”，最后建立带来源页与关联理由的知识图。适合已有学科基础、首次学习这门课的读者。

## 能做什么

- **逐页串讲**：先给课程总览与阅读主线，再解释每页的机制、例子、推导和应记住的内容。封面简写，关键内容展开，渐进演示页说明新增部分。
- **有依据的知识图**：合并同义概念，组织前置依赖、推导、应用、对比、问题与解决方案、证据支持等关系。每条关系说明理由，并可回到原页。
- **区分解释依据**：分别标注课件内容（`source`）、补充解释（`supplement`）、推断（`inference`）和不确定内容（`uncertain`）。
- **原页与讲义对照**：桌面并排、窄屏上下排列；支持图片放大、搜索、目录、页码跳转和上一页／下一页。
- **交互探索**：知识图支持缩放、平移、搜索和邻接高亮；讲义、概念与来源页双向跳转。
- **完整交付**：一次覆盖整份课件，保留原件，交付独立网页目录、ZIP 和可编辑的课程数据。

## 输入与输出

支持 **PPTX、课件 PDF**，以及经本机 LibreOffice 转换的旧版 **PPT**。一次处理一份课件；PPTX 按实际演示顺序关联页面与讲者备注。

生成的目录包含：

```text
my-course/
├── index.html       # 学习入口
├── lesson.json      # 可编辑的逐页讲义、概念与关系
├── source.json      # 原页信息与来源记录
├── pages/           # 原页图像
└── assets/          # 本地脚本、样式、公式字体
my-course.zip
```

解压 ZIP 后打开 `index.html` 即可阅读。成品无需账户、服务器、模型 API 或 CDN，课程数据直接嵌入网页；生成过程需要 AI 阅读课件、撰写讲义并审查内容。脚本负责提取、渲染、校验与打包。

**README 可切换中英文；学习网页界面目前为中文，讲解默认中文。** 可以在任务中指定讲解语言，网页界面没有语言切换按钮。

## 安装

先克隆仓库，再把完整技能目录复制到本机 skills 目录。以下命令不会覆盖已有的 `slide-study`：

```bash
git clone https://github.com/tzm224/LearnWeave.git
cd LearnWeave

skill_install_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skill_install_dir"
if [ -e "$skill_install_dir/slide-study" ]; then
  printf '%s\n' 'slide-study 已存在；请先备份或移走旧版本，再安装。'
else
  cp -R skills/slide-study "$skill_install_dir/slide-study"
fi
```

默认安装位置为 `~/.codex/skills/slide-study`；设置了 `CODEX_HOME` 时使用其下的 `skills/slide-study`。按[运行环境说明](skills/slide-study/references/setup.md)准备依赖后，在支持技能的 Codex 环境中调用。

## 使用

把课件提供给 Codex，并指定技能，例如：

```text
使用 $slide-study 处理这份 lecture.pdf。
请先理解全篇，再按原页序讲解每页内容、作用和前后衔接，
补齐必要的背景、例子与推导，建立可回溯来源页的知识图，
一次交付完整的本地离线学习网页和 ZIP。默认用中文讲解。
```

也可以说明自己的基础、想重点理解的章节、讲解语言或输出位置。长课件会在内部按章节处理，再统一术语、衔接与跨章关系。

## 生成环境

| 用途 | 依赖 |
| --- | --- |
| Python 脚本 | Python 3.10+、`pypdf`、`Pillow`；版本见 [requirements.txt](skills/slide-study/requirements.txt) |
| PDF 页面渲染 | Poppler 的 `pdftoppm` |
| 公式校验与网页打包 | Node.js；使用随包 KaTeX，无需 `npm install` |
| PPTX 渲染 | 已安装的 Codex Presentations 渲染器；不可用时使用 LibreOffice `soffice` + Poppler |
| 旧版 PPT 转换 | LibreOffice `soffice` |
| 成品阅读 | 现代浏览器，无需上述生成工具 |

依赖安装、工具路径配置和脚本命令见[运行环境说明](skills/slide-study/references/setup.md)。

## 质量与限制

页面覆盖、图片资源、概念双向引用、来源与公式由脚本校验；教学机制、推导与关系依据仍需对照原页审查。扫描 PDF 需要视觉阅读；静态页面不能完整保留动画或视频；转换器可能替换字体或改变布局。无法辨认的内容应标明具体页码。

开发时使用过 47 页与 134 页真实课件，以及包含非平凡页序、隐藏页和备注的 PPTX 材料进行验证；另有 17 项自动化测试。浏览器交互已通过本机 HTTP 预览检查，但当时浏览器工具禁止 `file://`，因此未实测双击本地文件与断网打开。未来生成任务应在允许的环境中验证，并如实报告未完成的检查。

## 仓库结构

```text
skills/slide-study/
├── SKILL.md          # 技能入口与工作流程
├── agents/           # Codex 界面元数据
├── references/       # 教学标准、内容契约与环境说明
├── scripts/          # 预处理、校验、构建与测试
├── assets/           # 网页模板与本地 KaTeX 资源
└── requirements.txt
```

- [技能说明](skills/slide-study/SKILL.md)
- [教学标准](skills/slide-study/references/teaching.md)
- [内容契约](skills/slide-study/references/content-model.md)

公式渲染使用随包保存的 **KaTeX 0.19.1**，其第三方许可见 [KaTeX LICENSE](skills/slide-study/assets/vendor/katex/LICENSE)，来源见 [provenance.json](skills/slide-study/assets/vendor/katex/provenance.json)。该许可适用于 KaTeX，不代表整个仓库的许可。
