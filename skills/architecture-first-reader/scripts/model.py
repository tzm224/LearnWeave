"""Shared loading and semantic checks. No extraction or teaching content generation."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from schema_check import SchemaChecker

SCHEMA_DIR = Path(__file__).resolve().parent.parent / 'schemas'
MARKDOWN_FILES = (
    'overview.md', 'document_map.md', 'knowledge_spine.md',
    'architecture_analysis.md', 'design_patterns.md',
)
DRAFT_FILES = (*MARKDOWN_FILES, 'knowledge_nodes.json', 'knowledge_graph.json')
OUTPUT_FILES = (*DRAFT_FILES, 'knowledge_graph.mmd')  # Original eight-file format


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON object key: {key}')
        result[key] = value
    return result


def _bad_constant(value: str) -> None:
    raise ValueError(f'non-finite JSON number: {value}')


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f'JSON number exceeds finite floating-point range: {value}')
    return parsed


def parse_json(content: str) -> Any:
    return json.loads(content, object_pairs_hook=_unique_object, parse_constant=_bad_constant, parse_float=_finite_float)


def read_json(path: Path) -> Any:
    return parse_json(path.read_text(encoding='utf-8'))


def read_bundle(directory: Path) -> tuple[dict, dict]:
    return read_json(directory / 'knowledge_nodes.json'), read_json(directory / 'knowledge_graph.json')


def has_cycle(pairs: list[tuple[str, str]]) -> bool:
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegrees: dict[str, int] = defaultdict(int)
    for start, end in pairs:
        outgoing[start].append(end)
        indegrees[start] += 0
        indegrees[end] += 1
    queue = deque(node for node, count in indegrees.items() if count == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for target in outgoing[node]:
            indegrees[target] -= 1
            if indegrees[target] == 0:
                queue.append(target)
    return visited != len(indegrees)


def check_data(nodes_data: Any, graph: Any) -> tuple[list[str], list[str]]:
    checker = SchemaChecker(SCHEMA_DIR)
    errors = [f'knowledge_nodes.json {e}' for e in checker.validate(nodes_data, 'knowledge-nodes.schema.json')]
    errors += [f'knowledge_graph.json {e}' for e in checker.validate(graph, 'knowledge-graph.schema.json')]
    warnings: list[str] = []
    if errors:
        return errors, warnings
    nodes = nodes_data['nodes']
    sources = nodes_data['source_refs']
    for name, records in [('nodes', nodes), ('source_refs', sources), ('edges', graph['edges'])]:
        duplicates = [key for key, count in Counter(record['id'] for record in records).items() if count > 1]
        if duplicates:
            errors.append(f'{name}: duplicate IDs: {", ".join(duplicates)}')
    by_id = {node['id']: node for node in nodes}
    source_ids = {source['id'] for source in sources}
    primary_ids = {source['id'] for source in sources if source['origin'] == 'primary'}
    if not primary_ids:
        errors.append('source_refs: at least one primary source location is required')
    coverage = nodes_data['document']['coverage']
    if coverage['status'] == 'complete' and coverage['gaps']:
        errors.append('document.coverage: complete cannot have gaps')
    if coverage['status'] == 'partial':
        if not coverage['gaps']:
            errors.append('document.coverage: partial must explain at least one gap')
        warnings.append('Source coverage is partial; report the listed gaps in the overview and document map')
    if graph['document_id'] != nodes_data['document']['id']:
        errors.append('document_id: graph and nodes refer to different documents')
    for node in nodes:
        for reference in node['source_refs']:
            if reference not in source_ids:
                errors.append(f'node {node["id"]}: unknown source ref {reference}')
    spine_ids = [step['node_id'] for step in graph['spine']]
    if len(set(spine_ids)) != len(spine_ids):
        errors.append('spine: duplicate node IDs')
    for node_id in spine_ids:
        if node_id not in by_id:
            errors.append(f'spine: unknown node {node_id}')
    for rank, level in enumerate(('L1', 'L2', 'L3')):
        expected = {node['id'] for node in nodes if int(node['level'][1]) <= rank + 1}
        actual = set(graph['views'][level])
        if actual != expected:
            errors.append(f'views.{level}: must match cumulative levels; missing={sorted(expected-actual)}, extra={sorted(actual-expected)}')
    macro_count = len(graph['views']['L1'])
    if macro_count > 15:
        warnings.append(f'L1 has {macro_count} nodes; consider regrouping the macro view (target about 5–15)')
    semantic_keys = set()
    containment_pairs = []
    dependency_pairs = []
    for edge in graph['edges']:
        start, end, relation = edge['source_id'], edge['target_id'], edge['relation']
        if start not in by_id or end not in by_id:
            errors.append(f'edge {edge["id"]}: unknown endpoint {start} -> {end}')
        if start == end:
            errors.append(f'edge {edge["id"]}: self-loops are not allowed')
        endpoints = tuple(sorted((start, end))) if relation == 'contrasts_with' else (start, end)
        semantic_key = (relation, *endpoints)
        if semantic_key in semantic_keys:
            errors.append(f'edge {edge["id"]}: duplicate semantic edge {semantic_key}')
        semantic_keys.add(semantic_key)
        for reference in edge['evidence_refs']:
            if reference not in source_ids:
                errors.append(f'edge {edge["id"]}: unknown evidence ref {reference}')
        if start in by_id and end in by_id:
            if relation == 'supports' and by_id[start]['type'] != 'evidence':
                errors.append(f'edge {edge["id"]}: supports must start at an evidence node')
            if relation == 'generalizes_to' and by_id[end]['type'] != 'pattern':
                errors.append(f'edge {edge["id"]}: generalizes_to must end at a pattern node')
            if relation == 'trades_off' and by_id[end]['type'] != 'tradeoff':
                errors.append(f'edge {edge["id"]}: trades_off must end at a tradeoff node')
        if relation == 'part_of':
            containment_pairs.append((start, end))
        if relation == 'depends_on':
            dependency_pairs.append((start, end))
    if has_cycle(containment_pairs):
        errors.append('part_of: containment relationships contain a cycle')
    if has_cycle(dependency_pairs):
        warnings.append('depends_on contains a cycle; check whether this is genuine mutual dependence or an accidental circular prerequisite')
    return errors, warnings
