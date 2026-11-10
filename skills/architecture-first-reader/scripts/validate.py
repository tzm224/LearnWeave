#!/usr/bin/env python3
"""Check structure, references, coverage declarations, and output consistency.

This does not verify that source text supports a claim, that all source pages
were actually inspected, or that an explanation is pedagogically correct.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from model import DRAFT_FILES, MARKDOWN_FILES, OUTPUT_FILES, check_data, read_bundle
from render_mermaid import render
from schema_check import SchemaError

MARKER = re.compile(r'\[(n|s):([^\]\n]+)\]')
SPINE_HEADING = re.compile(r'^##\s+\d+\.\s+.*?\[n:([^\]\n]+)\]\s*$', re.MULTILINE)
LOCAL_FRAGMENT = re.compile(r'\]\((?:\./)?([a-z_]+\.md)#((?:node|source)-[a-z][a-z0-9_-]*)\)')


def check_navigation(documents: dict[str, str]) -> list[str]:
    """Check explicit node/source anchors used by the supplied templates.

    This intentionally does not implement all Markdown or fetch external URLs.
    Human review still checks whether a source locator supports the claim.
    """
    errors = []
    anchors = {
        filename: set(re.findall(r'<a\s+id=[\"\']([^\"\']+)[\"\']\s*>', content))
        for filename, content in documents.items()
    }
    for filename, content in documents.items():
        for target, anchor in LOCAL_FRAGMENT.findall(content):
            if target not in documents:
                errors.append(f'{filename}: navigation target {target} is missing')
            elif anchor not in anchors[target]:
                errors.append(f'{filename}: navigation anchor {target}#{anchor} is missing')
    return errors


def check_manuscript(documents: dict, nodes: dict, graph: dict, *, legacy_mermaid: str | None = None) -> tuple[list[str], list[str]]:
    errors, warnings = check_data(nodes, graph)
    if errors:
        return errors, warnings
    if set(documents) != set(MARKDOWN_FILES):
        return ['The document bundle must contain the five named Markdown drafts'], warnings
    node_ids = {node['id'] for node in nodes['nodes']}
    source_ids = {source['id'] for source in nodes['source_refs']}
    for name, content in documents.items():
        if not isinstance(content, str) or not content.strip():
            return [f'{name}: expected nonempty Markdown text'], warnings
        for kind, identifier in MARKER.findall(content):
            if identifier not in (node_ids if kind == 'n' else source_ids):
                errors.append(f'{name}: unknown {kind} marker {identifier}')
    errors += check_navigation(documents)
    if 'knowledge_spine.md' in documents:
        actual = SPINE_HEADING.findall(documents['knowledge_spine.md'])
        expected = [step['node_id'] for step in graph['spine']]
        if actual != expected:
            errors.append('knowledge_spine.md: numbered ## headings must follow graph.spine exactly; '
                          f'expected {expected}, found {actual}')
    if 'document_map.md' in documents:
        mapped = {identifier for kind, identifier in MARKER.findall(documents['document_map.md']) if kind == 's'}
        missing = source_ids - mapped
        if missing:
            errors.append(f'document_map.md: missing source locations for {sorted(missing)}')
    if legacy_mermaid is not None:
        # File names are deliberately fixed by the contract; prose can vary freely.
        for name in OUTPUT_FILES[1:]:
            if not re.search(r'\]\((?:<)?(?:\./)?' + re.escape(name) + r'(?:#[^)>]*)?(?:>)?\)', documents['overview.md']):
                errors.append(f'overview.md: missing navigation link to {name}')
        if legacy_mermaid != render(nodes, graph):
            errors.append('knowledge_graph.mmd is stale or is not the default L1 view; regenerate with render_mermaid.py')
    return errors, warnings


def read_manuscript(directory: Path) -> tuple[dict, dict, dict]:
    missing = [f'Missing required output: {name}' for name in DRAFT_FILES if not (directory / name).is_file()]
    if missing:
        raise ValueError('\n'.join(missing))
    documents = {name: (directory / name).read_bytes().decode('utf-8') for name in MARKDOWN_FILES}
    nodes, graph = read_bundle(directory)
    return documents, nodes, graph


def validate_directory(directory: Path) -> tuple[list[str], list[str]]:
    try:
        documents, nodes, graph = read_manuscript(directory)
        return check_working_files(directory, documents, nodes, graph)
    except (OSError, ValueError) as exc:
        return [str(exc)], []


def check_working_files(directory: Path, documents: dict, nodes: dict, graph: dict) -> tuple[list[str], list[str]]:
    mmd = directory / 'knowledge_graph.mmd'
    mermaid = mmd.read_text(encoding='utf-8') if mmd.is_file() else None
    return check_manuscript(documents, nodes, graph, legacy_mermaid=mermaid)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path, help='Authoring directory, legacy analysis directory, or reader index.html')
    args = parser.parse_args(argv)
    try:
        path = args.path
        if path.is_dir() and (path / 'index.html').is_file() and not (path / 'knowledge_nodes.json').is_file():
            path = path / 'index.html'
        if path.is_file():
            from build_reader import read_reader
            _, warnings = read_reader(path)
            errors = []
        else:
            errors, warnings = validate_directory(path)
    except (OSError, ValueError, SchemaError) as exc:
        errors, warnings = [str(exc)], []
    for warning in warnings:
        print(f'WARNING: {warning}')
    for error in errors:
        print(f'ERROR: {error}', file=sys.stderr)
    if errors:
        print(f'FAILED: {len(errors)} error(s)', file=sys.stderr)
        return 1
    print('PASS: structure and references are consistent.')
    print('Content truth, source completeness, and design reasoning still require source-based review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
