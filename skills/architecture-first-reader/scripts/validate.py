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

from model import OUTPUT_FILES, check_data, read_bundle
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


def validate_directory(directory: Path) -> tuple[list[str], list[str]]:
    errors = [f'Missing required output: {name}' for name in OUTPUT_FILES if not (directory / name).is_file()]
    warnings: list[str] = []
    if not all((directory / name).is_file() for name in ('knowledge_nodes.json', 'knowledge_graph.json')):
        return errors, warnings
    try:
        nodes, graph = read_bundle(directory)
        data_errors, data_warnings = check_data(nodes, graph)
    except (OSError, ValueError, SchemaError) as exc:
        return errors + [str(exc)], warnings
    errors += data_errors
    warnings += data_warnings
    if data_errors:
        return errors, warnings
    node_ids = {node['id'] for node in nodes['nodes']}
    source_ids = {source['id'] for source in nodes['source_refs']}
    documents = {}
    for name in OUTPUT_FILES:
        if not name.endswith('.md') or not (directory / name).is_file():
            continue
        try:
            content = (directory / name).read_text(encoding='utf-8')
        except (OSError, UnicodeError) as exc:
            errors.append(f'{name}: {exc}')
            continue
        documents[name] = content
        if not content.strip():
            errors.append(f'{name}: file is empty')
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
    if 'overview.md' in documents:
        # File names are deliberately fixed by the contract; prose can vary freely.
        for name in OUTPUT_FILES[1:]:
            if not re.search(r'\]\((?:<)?(?:\./)?' + re.escape(name) + r'(?:#[^)>]*)?(?:>)?\)', documents['overview.md']):
                errors.append(f'overview.md: missing navigation link to {name}')
    mmd = directory / 'knowledge_graph.mmd'
    if mmd.is_file():
        try:
            if mmd.read_text(encoding='utf-8') != render(nodes, graph):
                errors.append('knowledge_graph.mmd is stale or is not the default L1 view; regenerate with render_mermaid.py')
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f'knowledge_graph.mmd: {exc}')
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Directory containing the eight analysis files')
    args = parser.parse_args(argv)
    errors, warnings = validate_directory(args.directory)
    for warning in warnings:
        print(f'WARNING: {warning}')
    for error in errors:
        print(f'ERROR: {error}', file=sys.stderr)
    if errors:
        print(f'FAILED: {len(errors)} error(s)', file=sys.stderr)
        return 1
    print('PASS: structure, references, and generated L1 Mermaid are consistent.')
    print('Content truth, source completeness, and design reasoning still require source-based review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
