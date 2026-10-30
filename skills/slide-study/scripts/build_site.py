#!/usr/bin/env python3
"""Build and package a validated offline course; never infer teaching content."""
import argparse
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from validate_lesson import read_json, validate_data
from prepare_source import binary, PreparationError

SKILL_DIR = Path(__file__).resolve().parent.parent
MARKER = '<meta name="generator" content="slide-study-v1">'


def embedded_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


class AssetRefs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        key = "src" if tag in {"script", "img"} else "href" if tag == "link" else None
        if key and values.get(key):
            self.refs.append(values[key])


def check_assets(folder):
    parser = AssetRefs()
    parser.feed((folder / "index.html").read_text(encoding="utf-8"))
    for ref in parser.refs:
        if ref.startswith("data:"):
            continue
        if re.match(r"(?:[a-z]+:|//|/)", ref, re.I):
            raise ValueError(f"Nonlocal template resource: {ref}")
        target = (folder / ref).resolve()
        if not target.is_relative_to(folder.resolve()) or not target.is_file():
            raise ValueError(f"Missing template resource: {ref}")
    for css in folder.rglob("*.css"):
        for ref in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", css.read_text(encoding="utf-8")):
            if ref.startswith("data:"):
                continue
            target = (css.parent / ref).resolve()
            if re.match(r"(?:[a-z]+:|//|/)", ref, re.I) or not target.is_relative_to(folder.resolve()) or not target.is_file():
                raise ValueError(f"Missing or nonlocal stylesheet resource: {ref}")


def build(source_path, lesson_path, output):
    source_path, lesson_path, output = map(lambda p: Path(p).resolve(), (source_path, lesson_path, output))
    lesson, manifest = read_json(lesson_path), read_json(source_path)
    errors = validate_data(lesson, manifest, source_path.parent)
    if errors:
        raise ValueError("Validation failed:\n" + "\n".join(errors))
    if output == source_path.parent or source_path.is_relative_to(output) or lesson_path.is_relative_to(output):
        raise ValueError("Choose an output directory separate from the input/working directory")
    if output.exists():
        entry = output / "index.html"
        if not entry.is_file() or MARKER not in entry.read_text(encoding="utf-8"):
            raise ValueError("Output already exists and is not a slide-study artifact; choose a new directory")
        existing = read_json(output / "source.json")
        if existing.get("source", {}).get("sha256") != manifest["source"]["sha256"]:
            raise ValueError("Output belongs to a different source; choose a new directory")
    templates = SKILL_DIR / "assets" / "web"
    vendor = SKILL_DIR / "assets" / "vendor" / "katex"
    required = [templates / x for x in ("index.html", "app.js", "style.css")]
    required += [vendor / x for x in ("katex.min.js", "katex.min.css", "contrib/auto-render.min.js", "LICENSE", "VERSION")]
    for path in required:
        if not path.is_file():
            raise ValueError(f"Missing bundled asset: {path}")
    if (vendor / "VERSION").read_text().strip() != "0.19.1":
        raise ValueError("Expected bundled KaTeX version 0.19.1")
    math_check = subprocess.run([binary("node"), str(SKILL_DIR / "scripts/validate_math.cjs"), str(lesson_path)], capture_output=True, text=True, timeout=120)
    if math_check.returncode:
        raise ValueError("Formula validation failed:\n" + (math_check.stdout or math_check.stderr))
    math_result = json.loads(math_check.stdout)
    output.parent.mkdir(parents=True, exist_ok=True)
    archive_path = output.with_name(output.name + ".zip")
    if archive_path.exists() and not output.exists():
        raise ValueError(f"Archive already exists without matching output directory: {archive_path}")
    with tempfile.TemporaryDirectory(prefix=".slide-study-build-", dir=output.parent) as temp:
        stage = Path(temp) / output.name
        stage.mkdir()
        (stage / "assets").mkdir()
        shutil.copy2(templates / "app.js", stage / "assets/app.js")
        shutil.copy2(templates / "style.css", stage / "assets/style.css")
        shutil.copytree(vendor, stage / "assets/vendor/katex")
        for page in manifest["pages"]:
            dest = stage / page["image"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path.parent / page["image"], dest)
        for name, value in (("source.json", manifest), ("lesson.json", lesson)):
            (stage / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        template = (templates / "index.html").read_text(encoding="utf-8")
        substitutions = {"__TITLE__": html.escape(lesson["title"]), "__LESSON_JSON__": embedded_json(lesson), "__SOURCE_JSON__": embedded_json(manifest)}
        for token in substitutions:
            if token not in template:
                raise ValueError(f"Template is missing placeholder {token}")
        output_html = re.sub(r"__TITLE__|__LESSON_JSON__|__SOURCE_JSON__", lambda match: substitutions[match.group()], template)
        if MARKER not in output_html:
            output_html = output_html.replace("<head>", "<head>\n  " + MARKER, 1)
        if MARKER not in output_html:
            raise ValueError("Template lacks an HTML head for its generator marker")
        (stage / "index.html").write_text(output_html, encoding="utf-8")
        check_assets(stage)
        temp_zip = Path(temp) / "bundle.zip"
        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=str(Path(output.name) / path.relative_to(stage)))
        # Only replace generator-owned files; retain unrelated user-added files.
        output.mkdir(exist_ok=True)
        for path in sorted(stage.rglob("*")):
            rel = path.relative_to(stage)
            dest = output / rel
            if dest.is_symlink() or not dest.resolve().is_relative_to(output):
                raise ValueError(f"Refusing to replace unsafe output path: {dest}")
            if path.is_dir():
                dest.mkdir(exist_ok=True)
            else:
                os.replace(path, dest)
        os.replace(temp_zip, archive_path)
    return {"index": str(output / "index.html"), "archive": str(archive_path), "pages": len(lesson["pages"]), "concepts": len(lesson["concepts"]), "relations": len(lesson["relations"]), "formulas_checked": math_result["formulas"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--lesson", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(args.source, args.lesson, args.output)
    except (OSError, ValueError, PreparationError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
