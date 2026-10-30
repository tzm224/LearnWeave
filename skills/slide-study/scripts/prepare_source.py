#!/usr/bin/env python3
"""Extract ordered source evidence and static page images for slide-study.

Requires pypdf and Pillow; PDF rendering uses Poppler. PPTX rendering prefers
the installed Presentations artifact-tool helper, with LibreOffice fallback.
All subprocesses use argument arrays. Input files are never changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PreparationError(RuntimeError):
    pass


def runtime_root() -> Path:
    override = os.environ.get("SLIDE_STUDY_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies"


def binary(name: str) -> str:
    specific = os.environ.get(f"SLIDE_STUDY_{name.upper()}")
    if specific:
        path = Path(specific).expanduser().resolve()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        raise PreparationError(f"Configured {name} is not executable: {path}")
    candidates = []
    if name == "node" and os.environ.get("RUNTIME_NODE"):
        candidates.append(Path(os.environ["RUNTIME_NODE"]))
    if os.environ.get("RUNTIME_BIN_DIR"):
        candidates.append(Path(os.environ["RUNTIME_BIN_DIR"]) / name)
    base = runtime_root()
    candidates.extend([base / "bin/override" / name, base / "bin/fallback" / name])
    if name == "node":
        candidates.insert(0, base / "node/bin/node")
    candidates.extend(Path(p) for p in [shutil.which(name)] if p)
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise PreparationError(f"Required executable {name!r} unavailable. Use load_workspace_dependencies or SLIDE_STUDY_{name.upper()}.")


def run(args: list[str], *, env: dict | None = None, timeout: int = 900) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, env=env, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PreparationError(f"Failed to run {Path(args[0]).name}: {exc}") from exc
    if result.returncode:
        details = (result.stderr or result.stdout).strip()[-2000:]
        raise PreparationError(f"{Path(args[0]).name} exited {result.returncode}: {details}")
    return result.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_dimensions(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            size = image.size
        if min(size) < 32:
            raise ValueError("image is too small")
        return size
    except Exception as exc:
        raise PreparationError(f"Missing or unreadable page image {path}: {exc}") from exc


def install_images(paths: list[Path], pages: list[dict], destination: Path) -> None:
    if len(paths) != len(pages):
        raise PreparationError(f"Rendered {len(paths)} images for {len(pages)} source pages; refusing incomplete/misaligned output.")
    destination.mkdir()
    for index, (path, entry) in enumerate(zip(paths, pages), 1):
        width, height = image_dimensions(path)
        filename = f"page-{index:04d}.png"
        shutil.copyfile(path, destination / filename)
        entry.update(image=f"pages/{filename}", width=width, height=height)


def render_pdf(path: Path, destination: Path, max_dimension: int) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    prefix = destination / "page"
    run([binary("pdftoppm"), "-png", "-scale-to", str(max_dimension), str(path), str(prefix)])
    paths = []
    for candidate in destination.glob("page-*.png"):
        match = re.fullmatch(r"page-(\d+)\.png", candidate.name)
        if match:
            paths.append((int(match[1]), candidate))
    paths.sort()
    numbers = [number for number, _ in paths]
    if numbers != list(range(1, len(paths) + 1)):
        raise PreparationError("PDF renderer returned non-contiguous page image numbers.")
    return [path for _, path in paths]


class PdfWarningCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.count = 0
        self.examples: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1
        message = record.getMessage()
        if len(self.examples) < 3 and message not in self.examples:
            self.examples.append(message)


def extract_pdf(path: Path) -> tuple[list[dict], str, list[str]]:
    logger = logging.getLogger("pypdf")
    collector = PdfWarningCollector()
    old_handlers, old_propagate, old_level = logger.handlers[:], logger.propagate, logger.level
    logger.handlers, logger.propagate, logger.level = [collector], False, logging.WARNING
    warnings: list[str] = []
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise PreparationError("PDF is password-protected; provide an accessible copy.")
        labels = reader.page_labels if "/PageLabels" in reader.trailer["/Root"] else None
        if labels:
            warnings.append("PDF logical page labels are retained separately; visually verify whether they match printed labels.")
        pages = []
        for number, page in enumerate(reader.pages, 1):
            page_warnings = []
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                text = ""
                page_warnings.append(f"Text extraction failed ({type(exc).__name__}); inspect the original page image.")
            if not text.strip():
                page_warnings.append("No extractable text. Read the rendered page visually; this is not evidence of an empty page.")
            pages.append({"page": number, "printed_page": labels[number - 1] if labels else None,
                          "text": text, "notes": "", "warnings": page_warnings})
        title = str((reader.metadata or {}).get("/Title", "") or "").strip() or path.stem
    finally:
        logger.handlers, logger.propagate, logger.level = old_handlers, old_propagate, old_level
    if collector.count:
        warnings.append(f"PDF parser reported {collector.count} recoverable warnings; verify page images. Examples: " + "; ".join(collector.examples))
    if not pages:
        raise PreparationError("Source contains no pages.")
    return pages, title, warnings


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def xml_from_zip(archive: ZipFile, member: str) -> ET.Element:
    try:
        info = archive.getinfo(member)
    except KeyError as exc:
        raise PreparationError(f"PPTX is missing required part: {member}") from exc
    if info.file_size > 50 * 1024 * 1024:
        raise PreparationError(f"PPTX XML part exceeds the supported 50 MiB limit: {member}")
    data = archive.read(member)
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise PreparationError(f"PPTX XML part contains a prohibited DTD/entity declaration: {member}")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise PreparationError(f"Invalid XML in {member}: {exc}") from exc


def relationship_part(member: str) -> str:
    p = PurePosixPath(member)
    return str(p.parent / "_rels" / (p.name + ".rels"))


def resolve_target(member: str, target: str) -> str:
    decoded = unquote(target)
    parts = urlsplit(decoded)
    if parts.scheme or parts.netloc or parts.query or parts.fragment or "\\" in decoded:
        raise PreparationError(f"Unsupported relationship target in {member}: {target!r}")
    base = "" if decoded.startswith("/") else posixpath.dirname(member)
    resolved = posixpath.normpath(posixpath.join(base, decoded.lstrip("/")))
    if resolved in ("", ".", "..") or resolved.startswith("../") or resolved.startswith("/"):
        raise PreparationError(f"Relationship escapes the package: {target!r}")
    return resolved


def relationships(archive: ZipFile, member: str) -> dict[str, dict]:
    path = relationship_part(member)
    if path not in archive.namelist():
        return {}
    root = xml_from_zip(archive, path)
    result = {}
    for element in root:
        if local_name(element.tag) != "Relationship":
            continue
        identifier = element.get("Id")
        if not identifier or identifier in result:
            raise PreparationError(f"Missing or duplicate relationship ID in {path}")
        result[identifier] = {"type": element.get("Type", ""), "target": element.get("Target", ""),
                              "external": element.get("TargetMode", "").lower() == "external"}
    return result


def paragraph_text(root: ET.Element) -> str:
    lines = []
    for paragraph in root.iter():
        if local_name(paragraph.tag) == "p":
            text = "".join(element.text or "" for element in paragraph.iter() if local_name(element.tag) == "t")
            if text.strip():
                lines.append(text)
    return "\n".join(lines)


def extract_notes(root: ET.Element) -> str:
    chunks = []
    for shape in root.iter():
        if local_name(shape.tag) != "sp":
            continue
        placeholder = next((element for element in shape.iter() if local_name(element.tag) == "ph"), None)
        if placeholder is not None and placeholder.get("type") in {"dt", "ftr", "hdr", "sldNum", "sldImg"}:
            continue
        text = paragraph_text(shape)
        if text:
            chunks.append(text)
    return "\n\n".join(chunks)


def extract_pptx(path: Path) -> tuple[list[dict], str, list[str], list[str]]:
    warnings = ["PPTX is shown as static rendered slides. Animation timing, video, interactive content and font fidelity require visual review."]
    hidden_parts = []
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise PreparationError("PPTX contains duplicate package entries.")
        if any(name.startswith("/") or "\\" in name or ".." in PurePosixPath(name).parts for name in names):
            raise PreparationError("PPTX contains unsafe package member paths.")
        presentation = xml_from_zip(archive, "ppt/presentation.xml")
        if local_name(presentation.tag) != "presentation":
            raise PreparationError("PPTX presentation part is invalid.")
        slide_list = next((element for element in presentation if local_name(element.tag) == "sldIdLst"), None)
        if slide_list is None or len(slide_list) == 0:
            raise PreparationError("Presentation contains no slides.")
        rels = relationships(archive, "ppt/presentation.xml")
        pages, used_parts = [], set()
        for number, slide_ref in enumerate(slide_list, 1):
            rid = next((value for key, value in slide_ref.attrib.items() if key.endswith("}id")), None)
            relation = rels.get(rid or "")
            if not relation or not relation["type"].endswith("/slide") or relation["external"]:
                raise PreparationError(f"Invalid slide relationship at position {number}.")
            member = resolve_target("ppt/presentation.xml", relation["target"])
            if member in used_parts:
                raise PreparationError(f"Duplicate source slide at position {number}.")
            used_parts.add(member)
            root = xml_from_zip(archive, member)
            page_warnings = []
            if root.get("show", "1") in {"0", "false"}:
                hidden_parts.append(member)
                page_warnings.append("Hidden slide retained in its original presentation position.")
            if any(local_name(element.tag) == "timing" for element in root.iter()):
                page_warnings.append("Contains animation/build timing; the static image may not reproduce every intermediate or final state.")
            if any(local_name(element.tag) in {"videoFile", "audioFile", "media"} for element in root.iter()):
                page_warnings.append("Contains media; playback content is not included in this static image.")
            if any(local_name(element.tag) in {"chart", "relIds"} for element in root.iter()):
                page_warnings.append("Chart/diagram labels may be absent from extracted text; inspect the rendered visual.")
            notes, printed = "", None
            for shape in root.iter():
                if local_name(shape.tag) != "sp":
                    continue
                ph = next((element for element in shape.iter() if local_name(element.tag) == "ph"), None)
                if ph is not None and ph.get("type") == "sldNum":
                    printed = paragraph_text(shape) or None
            note_rels = [r for r in relationships(archive, member).values() if r["type"].endswith("/notesSlide")]
            if len(note_rels) > 1:
                raise PreparationError(f"Slide {number} has more than one notes part.")
            if note_rels:
                rel = note_rels[0]
                if rel["external"]:
                    raise PreparationError(f"Slide {number} has an external notes relationship.")
                notes = extract_notes(xml_from_zip(archive, resolve_target(member, rel["target"])))
            text = paragraph_text(root)
            if not text.strip():
                page_warnings.append("No extractable slide text; inspect the rendered page visually.")
            pages.append({"page": number, "printed_page": printed, "text": text, "notes": notes, "warnings": page_warnings})
        title = path.stem
        if "docProps/core.xml" in names:
            core = xml_from_zip(archive, "docProps/core.xml")
            title_element = next((element for element in core if local_name(element.tag) == "title"), None)
            if title_element is not None and (title_element.text or "").strip():
                title = title_element.text.strip()
    return pages, title, warnings, hidden_parts


def rendering_copy(path: Path, output: Path, hidden_parts: list[str]) -> Path:
    if not hidden_parts:
        return path
    # Show hidden slides only in the throwaway render copy; source metadata keeps them hidden.
    with ZipFile(path) as archive, ZipFile(output, "w") as target:
        for info in archive.infolist():
            data = archive.read(info.filename)
            if info.filename in hidden_parts:
                # Preserve namespace declarations, including prefixes used only
                # by mc:Ignorable, which ElementTree serialization can discard.
                match = re.search(rb'<(?:[A-Za-z_][\w.-]*:)?sld\b[^>]*>', data)
                if match is None:
                    raise PreparationError(f"Cannot locate slide root in {info.filename}")
                opening = match.group()
                updated, replacements = re.subn(rb'\bshow\s*=\s*([\"\'])(?:0|false)\1', b'show="1"', opening, count=1)
                if replacements != 1:
                    raise PreparationError(f"Cannot normalize hidden slide {info.filename}")
                data = data[:match.start()] + updated + data[match.end():]
            target.writestr(info, data)
    return output


def artifact_renderer() -> Path | None:
    explicit = os.environ.get("SLIDE_STUDY_PPTX_RENDERER")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise PreparationError(f"PPTX renderer does not exist: {path}")
        return path
    codex = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    candidates = list((codex / "plugins/cache/openai-primary-runtime/presentations").glob("*/skills/presentations/container_tools/render_presentation.mjs"))
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def libreoffice_convert(path: Path, destination: Path, extension: str) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    profile = destination / "lo-profile"
    profile.mkdir()
    filter_name = extension
    if extension == "pdf":
        filter_name = 'pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}'
    elif extension == "pptx":
        filter_name = "pptx:Impress MS PowerPoint 2007 XML"
    run([binary("soffice"), f"-env:UserInstallation={profile.as_uri()}", "--headless", "--convert-to", filter_name, "--outdir", str(destination), str(path)])
    result = destination / (path.stem + "." + extension)
    if not result.is_file() or not result.stat().st_size:
        raise PreparationError(f"LibreOffice did not produce the expected {extension} file.")
    return result


def render_pptx(path: Path, destination: Path, count: int, max_dimension: int) -> tuple[list[Path], list[str]]:
    warnings = []
    helper = artifact_renderer()
    if helper:
        artifact_dir = destination / "artifact"
        artifact_dir.mkdir(parents=True)
        env = os.environ.copy()
        env.setdefault("RUNTIME_NODE_MODULES", str(runtime_root() / "node/node_modules"))
        try:
            with ZipFile(path) as archive:
                root = xml_from_zip(archive, "ppt/presentation.xml")
                size = next((element for element in root if local_name(element.tag) == "sldSz"), None)
                emu = max(int(size.get("cx", 0)), int(size.get("cy", 0))) if size is not None else 0
                scale = max_dimension / (emu / 914400 * 96) if emu else 1.5
            stdout = run([binary("node"), str(helper), "--input", str(path), "--output_dir", str(artifact_dir), "--scale", str(scale)], env=env)
            data = json.loads(stdout)
            images = [Path(p).resolve() for p in data["paths"]]
            if len(images) != count or any(not p.is_relative_to(artifact_dir.resolve()) for p in images):
                raise PreparationError("Artifact renderer returned an invalid page count or image path.")
            for image in images:
                image_dimensions(image)
            return images, warnings
        except (PreparationError, ValueError, KeyError, TypeError) as exc:
            warnings.append(f"Artifact PPTX rendering failed; used LibreOffice fallback. Reason: {str(exc)[:500]}")
    else:
        warnings.append("Installed artifact-tool PPTX renderer was not found; used LibreOffice fallback.")
    try:
        pdf = libreoffice_convert(path, destination / "libreoffice", "pdf")
    except PreparationError as exc:
        raise PreparationError("; ".join(warnings) + f"; LibreOffice fallback also failed: {exc}") from exc
    images = render_pdf(pdf, destination / "lo-images", max_dimension)
    if len(images) != count:
        raise PreparationError(f"LibreOffice rendered {len(images)} pages for {count} slides; refusing an incomplete deck.")
    warnings.append("LibreOffice rendering may substitute fonts or alter layout; inspect the page images.")
    return images, warnings


def prepare(input_path: Path, output: Path, max_dimension: int = 1800) -> dict:
    source = input_path.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_file():
        raise PreparationError(f"Input is not a file: {source}")
    suffix = source.suffix.lower()
    if suffix not in {".pdf", ".pptx", ".ppt"}:
        raise PreparationError("Supported inputs are .pdf, .pptx and legacy .ppt (converted locally).")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise PreparationError(f"Output must be new or empty; refusing to replace existing content: {output}")
    if not 320 <= max_dimension <= 6000:
        raise PreparationError("Maximum image dimension must be between 320 and 6000 pixels.")
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256(source)
    with tempfile.TemporaryDirectory(prefix=".slide-study-prepare-", dir=output.parent) as temporary:
        work = Path(temporary)
        package = work / "prepared"
        package.mkdir()
        working_source = source
        converted_warning = []
        if suffix == ".ppt":
            working_source = libreoffice_convert(source, work / "legacy-conversion", "pptx")
            converted_warning.append("Legacy .ppt converted to .pptx locally; conversion may change layout or unsupported features. Original input is preserved.")
        if suffix == ".pdf":
            pages, title, warnings = extract_pdf(working_source)
            images = render_pdf(working_source, work / "render", max_dimension)
        else:
            pages, title, warnings, hidden_parts = extract_pptx(working_source)
            render_source = rendering_copy(working_source, work / "visible-for-render.pptx", hidden_parts)
            images, render_warnings = render_pptx(render_source, work / "render", len(pages), max_dimension)
            warnings.extend(render_warnings)
        install_images(images, pages, package / "pages")
        manifest = {"schema_version": 1,
                    "source": {"filename": source.name, "format": suffix[1:], "sha256": digest, "page_count": len(pages), "title": title},
                    "warnings": converted_warning + warnings,
                    "pages": pages}
        (package / "source.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if sha256(source) != digest:
            raise PreparationError("Input file changed while processing; rerun against a stable source.")
        if output.exists():
            output.rmdir()
        package.rename(output)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory")
    parser.add_argument("--max-dimension", type=int, default=1800, help="Longest page-image dimension in pixels (default 1800)")
    args = parser.parse_args()
    try:
        result = prepare(args.input, args.output, args.max_dimension)
    except (PreparationError, OSError, ValueError, BadZipFile, PdfReadError) as exc:
        print(f"Preparation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"source_manifest": str(args.output.expanduser().resolve() / "source.json"),
                      "page_count": result["source"]["page_count"], "warnings": result["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
