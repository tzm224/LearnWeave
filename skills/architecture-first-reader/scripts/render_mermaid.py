#!/usr/bin/env python3
"""Project an existing validated knowledge graph into Mermaid. No inferred edges.

Only the Python standard library is needed. Rendering Mermaid visually requires
an existing Mermaid viewer; this script emits source, not an SVG or browser UI.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from model import check_data, read_bundle
from schema_check import SchemaError


def mermaid_id(node_id: str) -> str:
    # Hex encoding is stable, reversible, and does not collide for '-' vs '_'.
    return 'n_' + node_id.encode('utf-8').hex()


def escape_label(value: str) -> str:
    """Escape flowchart control syntax and HTML using Mermaid entity notation."""
    escaped = []
    for char in value:
        if char.isspace():
            escaped.append(' ')
        elif char in '&<>"\'`[]{}()|#;%\\':
            escaped.append(f'#{ord(char)};')
        elif ord(char) < 32 or ord(char) == 127:
            escaped.append(' ')
        else:
            escaped.append(char)
    return ''.join(escaped)


def select_nodes(nodes_data: dict, graph: dict, level: str, focus: str | None, hops: int) -> list[str]:
    selected = set(graph['views'][level])
    if hops < 0:
        raise ValueError('--hops must be nonnegative')
    if focus:
        all_ids = {node['id'] for node in nodes_data['nodes']}
        if focus not in all_ids:
            raise ValueError(f'Unknown focus node: {focus}')
        if focus not in selected:
            raise ValueError(f'Focus node {focus} is hidden at {level}; select a deeper --level')
        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in graph['edges']:
            left, right = edge['source_id'], edge['target_id']
            if left in selected and right in selected:
                adjacency[left].add(right)
                adjacency[right].add(left)
        reached, frontier = {focus}, {focus}
        for _ in range(hops):
            frontier = {neighbor for node in frontier for neighbor in adjacency[node]} - reached
            reached |= frontier
        selected &= reached
    # Preserve declared view order, rather than turning learning order into a sort.
    return [node_id for node_id in graph['views'][level] if node_id in selected]


def render(nodes_data: dict, graph: dict, level: str = 'L1', focus: str | None = None, hops: int = 1) -> str:
    errors, _ = check_data(nodes_data, graph)
    if errors:
        raise ValueError('\n'.join(errors))
    if level not in ('L1', 'L2', 'L3'):
        raise ValueError('level must be L1, L2, or L3')
    selected = select_nodes(nodes_data, graph, level, focus, hops)
    included = set(selected)
    by_id = {node['id']: node for node in nodes_data['nodes']}
    lines = [
        'flowchart LR',
        f'  %% View: {level}; only explicit edges with both endpoints visible.',
        '  %% Dashed nodes/edges denote AI inference. Contrasts have no arrow.',
        '  %% Source locations and edge rationales are in the canonical JSON files.',
    ]
    inferred_nodes = []
    for node_id in selected:
        node = by_id[node_id]
        label = f'{node["title"]} · {node["type"]} · {node["level"]}'
        if node['attribution'] == 'ai_inference':
            label += ' · AI inference'
            inferred_nodes.append(mermaid_id(node_id))
        lines.append(f'  %% node {node_id}; sources: {", ".join(node["source_refs"])}')
        lines.append(f'  {mermaid_id(node_id)}["{escape_label(label)}"]')
    inferred_edges = []
    index = 0
    for edge in graph['edges']:
        start, end = edge['source_id'], edge['target_id']
        if start not in included or end not in included:
            continue
        relation = edge['relation']
        label = relation
        if edge['attribution'] == 'ai_inference':
            label += ' / AI inference'
            inferred_edges.append(index)
        connector = '---' if relation == 'contrasts_with' else '-->'
        lines.append(f'  %% edge {edge["id"]}; sources: {", ".join(edge["evidence_refs"])}')
        lines.append(f'  {mermaid_id(start)} {connector}|"{escape_label(label)}"| {mermaid_id(end)}')
        index += 1
    if inferred_nodes:
        lines.append('  classDef inferred stroke-dasharray:5 5;')
        lines.append(f'  class {",".join(inferred_nodes)} inferred;')
    for edge_index in inferred_edges:
        lines.append(f'  linkStyle {edge_index} stroke-dasharray:5 5;')
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Directory containing both knowledge JSON files')
    parser.add_argument('--output', type=Path, help='Write Mermaid here; omitted means stdout')
    parser.add_argument('--level', choices=('L1', 'L2', 'L3'), default='L1')
    parser.add_argument('--focus', help='Show only this node and its visible neighbors')
    parser.add_argument('--hops', type=int, default=1)
    args = parser.parse_args(argv)
    try:
        nodes, graph = read_bundle(args.directory)
        result = render(nodes, graph, args.level, args.focus, args.hops)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result, encoding='utf-8')
            print(f'Wrote {args.output} ({args.level})')
        else:
            print(result, end='')
    except (OSError, ValueError, SchemaError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
