#!/usr/bin/env python3
"""Validate real page coverage, source assets and graph references, not prose quality."""
import argparse
import json
import re
import sys
from pathlib import Path

KINDS = {"source", "supplement", "inference", "uncertain"}
RELATIONS = {"prerequisite", "derivation", "application", "comparison", "problem_solution", "evidence"}


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_data(lesson, manifest, manifest_dir):
    errors = []

    def require(test, message):
        if not test:
            errors.append(message)
        return bool(test)

    def string(value, where, allow_empty=False):
        valid = require(isinstance(value, str) and (allow_empty or bool(value.strip())), f"{where}: expected {'possibly empty ' if allow_empty else 'nonempty '}string")
        if valid:
            require(not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value), f"{where}: unexpected control character; check LaTeX/JSON backslash escaping")
        return valid

    def array(value, where):
        if require(isinstance(value, list), f"{where}: expected array"):
            return value
        return []

    def obj(value, where):
        if require(isinstance(value, dict), f"{where}: expected object"):
            return value
        return {}

    lesson = obj(lesson, "lesson")
    manifest = obj(manifest, "manifest")
    require(lesson.get("schema_version") == 1, "lesson.schema_version must be 1")
    require(manifest.get("schema_version") == 1, "manifest.schema_version must be 1")
    source = obj(manifest.get("source"), "manifest.source")
    source_ref = obj(lesson.get("source"), "lesson.source")
    count = source.get("page_count")
    if not require(type(count) is int and count > 0, "manifest.source.page_count must be a positive integer"):
        count = 0
    for field in ("filename", "sha256", "page_count"):
        require(source_ref.get(field) == source.get(field), f"lesson.source.{field} does not match manifest")
    string(source.get("filename"), "source.filename")
    require(isinstance(source.get("sha256"), str) and re.fullmatch(r"[a-fA-F0-9]{64}", source.get("sha256", "")), "source.sha256 must be a SHA-256 hex digest")
    string(lesson.get("title"), "lesson.title")
    string(lesson.get("subtitle"), "lesson.subtitle", True)

    def pages(value, where, nonempty=True):
        values = array(value, where)
        if nonempty:
            require(bool(values), f"{where}: at least one source page is required")
        valid = [p for p in values if type(p) is int and 1 <= p <= count]
        require(len(valid) == len(values), f"{where}: page references must be integers within 1..{count}")
        require(len(set(valid)) == len(valid), f"{where}: duplicate page references")
        return set(valid)

    def provenance(value, where):
        require(isinstance(value, str) and value in KINDS, f"{where}: expected one of {sorted(KINDS)}")

    def block(value, where):
        data = obj(value, where)
        provenance(data.get("kind"), f"{where}.kind")
        string(data.get("text"), f"{where}.text")
        if "title" in data:
            string(data["title"], f"{where}.title", True)

    overview = obj(lesson.get("overview"), "overview")
    string(overview.get("summary"), "overview.summary")
    for name in ("objectives", "prerequisites"):
        for i, value in enumerate(array(overview.get(name), f"overview.{name}")):
            string(value, f"overview.{name}[{i}]")
    story_pages = set()
    for i, section in enumerate(array(overview.get("storyline"), "overview.storyline")):
        section = obj(section, f"storyline[{i}]")
        string(section.get("title"), f"storyline[{i}].title")
        string(section.get("summary"), f"storyline[{i}].summary")
        story_pages |= pages(section.get("pages"), f"storyline[{i}].pages")
    require(story_pages == set(range(1, count + 1)), "overview.storyline must cover every source page")

    source_pages = array(manifest.get("pages"), "manifest.pages")
    lesson_pages = array(lesson.get("pages"), "lesson.pages")
    expected = list(range(1, count + 1))
    for collection, name in ((source_pages, "manifest.pages"), (lesson_pages, "lesson.pages")):
        identities = [p.get("page") if isinstance(p, dict) else None for p in collection]
        require(identities == expected and all(type(p) is int for p in identities), f"{name}: expected every physical page exactly once in original order 1..{count}")

    root = Path(manifest_dir).resolve()
    image_paths = set()
    try:
        from PIL import Image
    except ImportError:
        Image = None
        errors.append("Pillow is required to verify source images; use the bundled Python runtime")
    for i, item in enumerate(source_pages):
        item = obj(item, f"manifest.pages[{i}]")
        name = f"source page {item.get('page', i + 1)}"
        rel = item.get("image")
        if not string(rel, f"{name}.image"):
            continue
        target = (root / rel).resolve()
        safe = not Path(rel).is_absolute() and ".." not in Path(rel).parts and Path(rel).parts[0] == "pages" and target.is_relative_to(root)
        if not require(safe, f"{name}: image must stay in source pages/ directory"):
            continue
        require(rel not in image_paths, f"{name}: duplicate image path {rel}")
        image_paths.add(rel)
        if not require(target.is_file(), f"{name}: missing image {rel}"):
            continue
        if Image:
            try:
                with Image.open(target) as image:
                    dims = image.size
                    require(image.format in {"PNG", "JPEG", "WEBP"}, f"{name}: unsupported image format")
                    image.verify()
                require(dims == (item.get("width"), item.get("height")), f"{name}: image dimensions do not match manifest")
            except Exception as exc:
                errors.append(f"{name}: unreadable image: {exc}")
        label = item.get("printed_page")
        require(label is None or isinstance(label, str), f"{name}.printed_page: expected string or null")

    concept_records = array(lesson.get("concepts"), "concepts")
    concept_pages = {}
    for i, value in enumerate(concept_records):
        value = obj(value, f"concepts[{i}]")
        cid = value.get("id")
        if not string(cid, f"concepts[{i}].id"):
            continue
        require(cid not in concept_pages, f"duplicate concept ID {cid}")
        for key in ("label", "description", "group"):
            string(value.get(key), f"concept {cid}.{key}")
        provenance(value.get("kind"), f"concept {cid}.kind")
        concept_pages[cid] = pages(value.get("pages"), f"concept {cid}.pages")

    reverse_refs = {cid: set() for cid in concept_pages}
    for i, value in enumerate(lesson_pages):
        value = obj(value, f"lesson.pages[{i}]")
        page = value.get("page")
        for key in ("title", "section"):
            string(value.get(key), f"page {page}.{key}")
        blocks = array(value.get("blocks"), f"page {page}.blocks")
        require(bool(blocks), f"page {page}: at least one explanatory block is required")
        for j, value_block in enumerate(blocks):
            block(value_block, f"page {page}.blocks[{j}]")
        for key in ("role", "bridge_prev", "bridge_next", "takeaway"):
            block(value.get(key), f"page {page}.{key}")
        ids = array(value.get("concept_ids"), f"page {page}.concept_ids")
        seen = set()
        for cid in ids:
            if not string(cid, f"page {page}.concept_ids"):
                continue
            require(cid not in seen, f"page {page}: duplicate concept {cid}")
            seen.add(cid)
            if require(cid in concept_pages, f"page {page}: unknown concept {cid}") and type(page) is int:
                reverse_refs[cid].add(page)
        if "printed_page" in value:
            require(value["printed_page"] is None or isinstance(value["printed_page"], str), f"page {page}.printed_page must be a string or null")
    for cid, refs in concept_pages.items():
        require(refs == reverse_refs[cid], f"concept {cid}: pages {sorted(refs)} disagree with page concept_ids {sorted(reverse_refs[cid])}")

    relation_ids = set()
    for i, value in enumerate(array(lesson.get("relations"), "relations")):
        value = obj(value, f"relations[{i}]")
        rid = value.get("id")
        if not string(rid, f"relations[{i}].id"):
            continue
        require(rid not in relation_ids, f"duplicate relation ID {rid}")
        relation_ids.add(rid)
        for key in ("label", "explanation"):
            string(value.get(key), f"relation {rid}.{key}")
        provenance(value.get("kind"), f"relation {rid}.kind")
        require(isinstance(value.get("type"), str) and value["type"] in RELATIONS, f"relation {rid}: invalid type")
        evidence = pages(value.get("pages"), f"relation {rid}.pages")
        for key in ("from", "to"):
            cid = value.get(key)
            if require(isinstance(cid, str) and cid in concept_pages, f"relation {rid}.{key}: unknown concept"):
                require(bool(evidence & concept_pages[cid]), f"relation {rid}: evidence must include a page from {key} concept {cid}")
        require(value.get("from") != value.get("to"), f"relation {rid}: self edges are not supported")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson", type=Path)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    try:
        lesson, manifest = read_json(args.lesson), read_json(args.source)
        errors = validate_data(lesson, manifest, args.source.parent)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"valid": True, "pages": len(lesson["pages"]), "concepts": len(lesson["concepts"]), "relations": len(lesson["relations"]), "note": "Structural and asset checks passed; teaching quality requires source review."}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
