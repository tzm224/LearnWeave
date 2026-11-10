#!/usr/bin/env python3
"""Build or recover a self-contained architecture-first-reader HTML analysis."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

from model import MARKDOWN_FILES, parse_json, read_json
from schema_check import SchemaError
from validate import check_manuscript, check_working_files, read_manuscript

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
FORMAT_VERSION = 1
ORIGIN_FILE = '.reader-origin.json'
TEMPLATE_TOKEN = re.compile(r'__(?:TITLE|STYLE|SCRIPT|NAV|ARTICLE|PAYLOAD)__')


class ReaderMarkup(HTMLParser):
    """Inspect markup without executing scripts or opening any source files."""

    def __init__(self, markup: str) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.fragments: set[str] = set()
        self.steps: list[str] = []
        self.errors: list[str] = []
        self.source_links: dict[str, str] = {}
        self.math = False
        self.capturing_payload = False
        self.payload_text: list[str] = []
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        identifier = values.get('id')
        if identifier:
            if identifier in self.ids:
                self.errors.append(f'Duplicate HTML anchor: {identifier}')
            self.ids.add(identifier)
            if identifier.startswith('step-'):
                self.steps.append(identifier.removeprefix('step-'))
        href = values.get('href') or ''
        if tag == 'a' and href.startswith('#') and len(href) > 1:
            self.fragments.add(unquote(href[1:]))
        source_id = values.get('data-original-source')
        if tag == 'a' and source_id and href and not href.startswith('#'):
            self.source_links.setdefault(source_id, href)
        if 'math' in (values.get('class') or '').split():
            self.math = True
        if tag == 'script':
            self.capturing_payload = identifier == 'reader-data' and values.get('type') == 'application/json'
        resource = href if tag == 'link' else values.get('src')
        if resource and not resource.startswith('data:'):
            self.errors.append(f'Automatically loaded resource is not embedded: {resource}')

    def handle_data(self, data: str) -> None:
        if self.capturing_payload:
            self.payload_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script':
            self.capturing_payload = False

    def check_links(self) -> None:
        missing = self.fragments - self.ids
        if missing:
            self.errors.append(f'Unresolved HTML anchor(s): {", ".join(sorted(missing))}')
        if self.errors:
            raise ValueError('\n'.join(self.errors))

    def check_spine(self, graph: dict) -> None:
        if self.steps != [step['node_id'] for step in graph['spine']]:
            raise ValueError('Rendered article steps do not match the learning spine')
        required = {'overview', 'spine', 'analysis', 'patterns', 'sources', 'graph', 'reader-data'}
        if required - self.ids:
            raise ValueError(f'Reader sections missing: {", ".join(sorted(required - self.ids))}')


def read_reader(path: Path) -> tuple[dict, list[str]]:
    markup = ReaderMarkup(path.read_text(encoding='utf-8'))
    markup.check_links()
    if not markup.payload_text:
        raise ValueError('Missing embedded architecture-first-reader data')
    payload = parse_json(''.join(markup.payload_text))
    if not isinstance(payload, dict) or type(payload.get('format_version')) is not int or payload['format_version'] != FORMAT_VERSION:
        raise ValueError('Unsupported HTML reader data format')
    if not isinstance(payload.get('documents'), dict) or set(payload['documents']) != set(MARKDOWN_FILES):
        raise ValueError('Expected the five named Markdown drafts in the HTML')
    if not isinstance(payload.get('source_base'), str) or not payload['source_base']:
        raise ValueError('Missing source link base in the HTML')
    errors, warnings = check_manuscript(payload['documents'], payload.get('nodes'), payload.get('graph'))
    if errors:
        raise ValueError('\n'.join(errors))
    markup.check_spine(payload['graph'])
    return payload, warnings


def relative_base(base: Path, directory: Path) -> str:
    try:
        return Path(os.path.relpath(base, directory)).as_posix()
    except ValueError:  # Different volumes on Windows cannot share a relative path.
        return str(base)


def read_source_base(directory: Path, override: Path | None) -> Path:
    if override:
        return override.resolve()
    origin = directory / ORIGIN_FILE
    if origin.exists():
        metadata = read_json(origin)
        if not isinstance(metadata, dict) or not isinstance(metadata.get('source_base'), str):
            raise ValueError(f'{ORIGIN_FILE}: expected source_base as a path')
        return (directory / metadata['source_base']).resolve()
    return directory


def json_for_script(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return raw.replace('&', r'\u0026').replace('<', r'\u003c').replace('>', r'\u003e').replace('\u2028', r'\u2028').replace('\u2029', r'\u2029')


def build(directory: Path, output: Path, source_base: Path | None = None) -> tuple[Path, list[str]]:
    if sys.version_info < (3, 10):
        raise ValueError('Building the HTML reader requires Python 3.10 or newer')
    from reader_article import render_article, source_href

    directory = directory.resolve()
    documents, nodes, graph = read_manuscript(directory)
    errors, warnings = check_working_files(directory, documents, nodes, graph)
    if errors:
        raise ValueError('\n'.join(errors))
    if output.is_symlink():
        raise ValueError('Choose an output directory that is not a symlink')
    output = output.resolve()
    origin = read_source_base(directory, source_base)
    article, nav = render_article(documents, nodes, graph, origin, output)
    content = ReaderMarkup(article)
    source_links = {}
    for source in nodes['source_refs']:
        source_id = source['id']
        href = content.source_links.get(source_id) or source_href(source['uri'], origin, output)
        if href:
            source_links[source_id] = href
    payload = dict(format_version=FORMAT_VERSION, documents=documents, nodes=nodes, graph=graph,
                   source_base=relative_base(origin, output), source_links=source_links)
    reader_assets = ASSETS / 'reader'
    css = '\n'.join((reader_assets / f).read_text(encoding='utf-8') for f in ('reader.css', 'graph.css'))
    scripts = [(reader_assets / f).read_text(encoding='utf-8') for f in ('graph.js', 'reader.js')]
    if content.math:
        katex = ASSETS / 'vendor' / 'katex'
        license_text = (katex / 'LICENSE').read_text(encoding='utf-8')
        scripts.insert(0, f'/*\n{license_text}\n*/\n' + (katex / 'katex.min.js').read_text(encoding='utf-8'))
    values = {'__TITLE__': html.escape(nodes['document']['title']), '__STYLE__': css, '__SCRIPT__': '\n'.join(scripts),
              '__ARTICLE__': article, '__NAV__': nav, '__PAYLOAD__': json_for_script(payload)}
    template = (reader_assets / 'template.html').read_text(encoding='utf-8')
    if set(TEMPLATE_TOKEN.findall(template)) != set(values):
        raise ValueError('Reader template is missing a required placeholder')
    result = TEMPLATE_TOKEN.sub(lambda m: values[m.group()], template)
    markup = ReaderMarkup(result)
    markup.check_links()
    markup.check_spine(graph)

    output.parent.mkdir(parents=True, exist_ok=True)
    entry = output / 'index.html'
    existing = list(output.iterdir()) if output.exists() else []
    if existing:
        if existing != [entry] or entry.is_symlink() or not entry.is_file():
            raise ValueError('Use an empty delivery directory or update an existing reader for the same document')
        previous, _ = read_reader(entry)
        if previous['nodes']['document']['id'] != nodes['document']['id']:
            raise ValueError('The existing reader belongs to a different document')
    # Keep incomplete output outside the delivery folder; publish only a complete file.
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.reader-build-') as tmp:
        staged = Path(tmp) / 'reader'
        staged.mkdir()
        (staged / 'index.html').write_text(result, encoding='utf-8')
        if existing:
            os.replace(staged / 'index.html', entry)
        else:
            publish_directory(staged, output)
    return entry, warnings


def publish_directory(staged: Path, output: Path) -> None:
    """An atomic rename also refuses to replace a concurrently populated directory."""
    if output.exists() and os.name == 'nt':
        output.rmdir()  # Windows rename cannot replace an empty directory.
    staged.rename(output)


def extract(entry: Path, output: Path) -> tuple[Path, list[str]]:
    payload, warnings = read_reader(entry)
    if output.is_symlink():
        raise ValueError('Choose an extraction directory that is not a symlink')
    output = output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Extract into a new or empty directory to preserve existing drafts')
    output.parent.mkdir(parents=True, exist_ok=True)
    origin = (entry.resolve().parent / payload['source_base']).resolve()
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.reader-extract-') as tmp:
        staged = Path(tmp) / 'drafts'
        staged.mkdir()
        for name in MARKDOWN_FILES:
            (staged / name).write_bytes(payload['documents'][name].encode('utf-8'))
        data = {'knowledge_nodes.json': payload['nodes'], 'knowledge_graph.json': payload['graph']}
        if origin != output:
            data[ORIGIN_FILE] = {'source_base': relative_base(origin, output)}
        for name, obj in data.items():
            (staged / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        publish_directory(staged, output)
    return output, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    package = actions.add_parser('build', help='Publish a reader from the seven drafts or a legacy analysis')
    package.add_argument('directory', type=Path)
    package.add_argument('--output', type=Path, required=True, help='Directory for the single index.html')
    package.add_argument('--source-base', type=Path, help='Rebind the base directory of relative original-material links')
    recover = actions.add_parser('extract', help='Recover editable drafts from a reader')
    recover.add_argument('index', type=Path)
    recover.add_argument('--output', type=Path, required=True, help='New or empty draft directory')
    args = parser.parse_args(argv)
    try:
        if args.action == 'build':
            result, warnings = build(args.directory, args.output, args.source_base)
        else:
            result, warnings = extract(args.index, args.output)
    except (OSError, ValueError, SchemaError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    for warning in warnings:
        print(f'WARNING: {warning}', file=sys.stderr)
    print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
