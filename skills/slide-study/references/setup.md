# Runtime setup

These tools are needed to **create** a course. Reading a generated course only requires a modern browser: unzip the delivered archive and open `index.html`.

## Dependencies

| Component | Required for |
| --- | --- |
| Python 3.10 or later | Source preparation, content validation and packaging |
| `pypdf` and `Pillow` | PDF text extraction and page-image validation |
| Node.js | Formula validation using the bundled KaTeX; no `npm install` needed |
| Poppler (`pdftoppm`) | Rendering PDF pages, including PDFs exported by LibreOffice |
| LibreOffice (`soffice`) | Legacy `.ppt` conversion; PPTX rendering when the optional Codex Presentations renderer is unavailable |

The validated environment used Python 3.12.14, Node.js 24.19.0, pypdf 6.10.0 and Pillow 12.3.0 on macOS. Other platforms have not been validated end to end.

If the agent environment provides `load_workspace_dependencies`, use it to locate its bundled tools first. Otherwise install Python packages in a virtual environment and make the required executables available on `PATH`.

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r skills/slide-study/requirements.txt
```

Install Node.js, Poppler and, when needed, LibreOffice using your normal system package manager. They are separate from the Python requirements. Use the same Python interpreter for preparation, validation and packaging.

## Executable paths

The scripts look for executables in the bundled Codex runtime and on `PATH`. Explicit paths take priority:

| Variable | Value |
| --- | --- |
| `SLIDE_STUDY_NODE` | Absolute path to the `node` executable |
| `SLIDE_STUDY_PDFTOPPM` | Absolute path to the `pdftoppm` executable |
| `SLIDE_STUDY_SOFFICE` | Absolute path to the `soffice` executable |
| `SLIDE_STUDY_RUNTIME_DIR` | Optional custom Codex runtime dependencies directory |
| `SLIDE_STUDY_PPTX_RENDERER` | Optional path to the Codex Presentations `render_presentation.mjs` helper, with its matching runtime dependencies |

For example, a standard macOS LibreOffice installation can be selected with:

```bash
export SLIDE_STUDY_SOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"
```

The optional Presentations helper is discovered under the Codex plugin cache. It is not redistributed in this repository. When it is unavailable or fails, the scripts try LibreOffice and record the fallback in `source.json`.

## Pipeline

Run from the repository root, using the configured Python environment:

```bash
python skills/slide-study/scripts/prepare_source.py \
  /path/to/lecture.pdf --output work/prepared
```

`work/prepared` must be new or empty. It receives `source.json` and a `pages/` directory. Original input files are preserved.

Next, the AI reads the full source and page images and writes `work/lesson.json` following the [content model](content-model.md) and [teaching standards](teaching.md). This is a required authoring step: the preprocessing scripts do not generate explanations or concept relationships.

```bash
python skills/slide-study/scripts/validate_lesson.py \
  work/lesson.json --source work/prepared/source.json

python skills/slide-study/scripts/build_site.py \
  --source work/prepared/source.json \
  --lesson work/lesson.json \
  --output output/lecture
```

The build validates all formulas with the bundled KaTeX 0.19.1, then writes `output/lecture/index.html` and `output/lecture.zip`. The output folder includes editable `lesson.json` and `source.json`. After editing the course data, rebuild to update the HTML's embedded data.

Missing pages, invalid references, damaged images or unrenderable formulas cause validation to fail. Fix these errors before treating the result as complete.

## Verification

```bash
python -m unittest discover -s skills/slide-study/scripts/tests -v
```

The tests create temporary fixtures; they do not need private course files. They cover slide order and notes, source preservation, page coverage, graph references, formula errors and offline asset packaging. Passing structural tests does not establish teaching quality: compare the explanations and graph evidence with the original pages.

Check a generated course in a browser, including navigation, formulas, images, graph details, narrow layouts and keyboard use. If browser automation rejects `file://`, use only an allowed loopback HTTP preview for interaction checks and disclose that direct local-file opening has not been tested. Stop any preview server you started after verification.

## Reading limitations

- Scanned PDFs may have no extractable text; the AI must inspect the rendered images.
- PPTX rendering is static. It cannot demonstrate full animation, video or interactive media.
- A renderer may substitute fonts or change layout. Review the original-page images and recorded warnings.
- Formula syntax validation cannot verify mathematical correctness.
- The generated reader interface is Chinese. The repository's Chinese/English README links do not switch the reader UI.

## Third-party assets

KaTeX 0.19.1 is bundled locally with its scripts, styles and fonts. Its [MIT license](../assets/vendor/katex/LICENSE) and [package provenance](../assets/vendor/katex/provenance.json) are preserved. This license applies to KaTeX; it does not assign a license to the rest of the repository.
