"""Turn the five authored documents into a linked article. Source text is never executed."""
from __future__ import annotations

import os
import posixpath
import re
import sys
from dataclasses import dataclass, field
from html import escape, unescape
from pathlib import Path, PureWindowsPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import url2pathname

sys.path.insert(0, str(Path(__file__).resolve().parent / 'vendor'))
import mistune
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table


SECTIONS = {
    'overview.md': 'overview',
    'knowledge_spine.md': 'spine',
    'architecture_analysis.md': 'analysis',
    'design_patterns.md': 'patterns',
    'document_map.md': 'sources',
}
GRAPH_FILES = {'knowledge_graph.mmd', 'knowledge_graph.json', 'knowledge_nodes.json'}
MARKER = re.compile(r'\[([ns]):([a-z][a-z0-9_-]*)\]')
ANCHOR = r"""^ {0,3}<a\s+id=(?P<anchor_quote>["'])(?P<anchor_id>[\w.-]+)(?P=anchor_quote)\s*>\s*</a>[ \t]*(?:\n|$)"""


def source_href(uri: str, source_dir: Path, output_dir: Path) -> str | None:
    """Rebase an original reference while allowing only local files and HTTP(S)."""
    uri = unescape(uri).strip()
    if re.match(r'^[A-Za-z]:[\\/]', uri):
        uri = PureWindowsPath(uri).as_uri()
    normalized = unquote(uri).strip()
    if not uri or any(ord(ch) < 32 for ch in normalized) or '\\' in normalized:
        return None
    try:
        parts = urlsplit(uri)
        scheme = urlsplit(normalized).scheme.lower()
    except ValueError:
        return None
    if scheme in {'http', 'https'}:
        return uri if parts.scheme == scheme and parts.hostname else None
    if parts.netloc not in ('', 'localhost') or (parts.netloc and scheme != 'file'):
        return None
    if scheme not in {'', 'file'} or normalized.startswith('//') or not parts.path:
        return None
    path = url2pathname(parts.path) if scheme == 'file' else unquote(parts.path)
    if scheme == 'file':
        if os.name != 'nt' and re.match(r'^/[A-Za-z]:/', path):
            return uri
        if not Path(path).is_absolute():
            return None
    target = source_dir / path
    try:
        relative = os.path.relpath(target, output_dir)
    except ValueError:  # Different Windows drives have no relative path.
        return target.absolute().as_uri() + urlunsplit(('', '', '', parts.query, parts.fragment))
    return urlunsplit(('', '', quote(Path(relative).as_posix(), safe='/'), parts.query, parts.fragment))


def reader_syntax(md):
    def anchor(block, match, state):
        state.append_token({'type': 'reader_anchor', 'raw': match['anchor_id']})
        return match.end()

    def tex(inline, match, state):
        display = match['display_tex'] is not None
        state.append_token({'type': 'block_math' if display else 'inline_math',
                            'raw': match['display_tex'] if display else match['inline_tex']})
        return match.end()

    md.block.register('reader_anchor', ANCHOR, anchor, before='raw_html')
    md.inline.register('reader_tex', r'\\\((?P<inline_tex>[\s\S]*?)\\\)|\\\[(?P<display_tex>[\s\S]*?)\\\]',
                       tex, before='escape')


def plain(token):
    if 'raw' in token:
        return token['raw']
    return ''.join(plain(child) for child in token.get('children', []))


def links(tokens):
    for token in tokens:
        if token['type'] == 'link':
            yield token['attrs']['url']
        yield from links(token.get('children', []))


@dataclass
class Part:
    heading: dict | None = None
    anchors: list[str] = field(default_factory=list)
    body: list[dict] = field(default_factory=list)
    node: str = ''
    source: str = ''
    target: str = ''
    step: bool = False

    @property
    def level(self):
        return self.heading['attrs']['level'] if self.heading else 0

    @property
    def title(self):
        return MARKER.sub('', plain(self.heading)).strip() if self.heading else ''


class Document:
    def __init__(self, name, tokens, spine):
        self.route = SECTIONS[name]
        self.parts = [Part()]
        self.targets = {}
        anchors = []
        for token in tokens:
            kind = token['type']
            if kind == 'reader_anchor':
                anchors.append(token['raw'])
            elif kind == 'blank_line':
                continue
            elif kind == 'heading' or anchors:
                part = Part(token if kind == 'heading' else None, anchors)
                if kind != 'heading':
                    part.body.append(token)
                self.parts.append(part)
                anchors = []
            else:
                self.parts[-1].body.append(token)
        if anchors:
            self.parts.append(Part(anchors=anchors))

        # Reserve declared anchors first. An earlier heading may merely mention the same node.
        for part in self.parts:
            for anchor in part.anchors:
                if anchor in self.targets:
                    raise ValueError(f'{name}: duplicate anchor {anchor}')
                self.targets[anchor] = f'{self.route}-{anchor}'
        for part in self.parts:
            marks = MARKER.findall(plain(part.heading)) if part.heading else []
            part.node = next((a[5:] for a in part.anchors if a.startswith('node-')),
                             next((i for k, i in marks if k == 'n'), ''))
            if self.route == 'sources':
                part.source = next((a[7:] for a in part.anchors if a.startswith('source-')),
                                   next((i for k, i in marks if k == 's'), ''))
            if self.route == 'spine' and part.level == 2:
                step = re.fullmatch(r'\d+\.\s+.*\[n:([a-z][a-z0-9_-]*)\]\s*', plain(part.heading), re.DOTALL)
                if step and step[1] in spine:
                    part.node, part.step = step[1], True
            if part.step:
                part.target = f'step-{part.node}'
            elif part.anchors:
                part.target = self.targets[part.anchors[0]]
            # A marker-bearing heading can supply a deep link even without an explicit anchor.
            inferred = ''
            if self.route in {'analysis', 'patterns'} and part.node:
                inferred = f'node-{part.node}'
            if part.source:
                inferred = f'source-{part.source}'
            if inferred and inferred not in self.targets:
                self.targets[inferred] = part.target or f'{self.route}-{inferred}'
                part.target = self.targets[inferred]

        for part in self.parts:
            if not part.heading:
                continue
            slug = re.sub(r'[^\w\s-]', '', part.title.lower()).strip().replace(' ', '-') or 'section'
            unique, n = slug, 0
            while unique in self.targets or f'{self.route}-heading-{unique}' in self.targets.values():
                n += 1
                unique = f'{slug}-{n}'
            self.targets[unique] = part.target or f'{self.route}-heading-{unique}'
            part.target = self.targets[unique]

    def detail(self, anchor):
        target = self.targets.get(anchor)
        for i, part in enumerate(self.parts):
            if target and (part.target == target or anchor in part.anchors):
                end = i + 1
                while end < len(self.parts) and self.parts[end].level > part.level:
                    end += 1
                return self.parts[i:end]
        return []


class ArticleRenderer(mistune.HTMLRenderer):
    def __init__(self, documents, nodes_data, graph, source_dir, output_dir):
        super().__init__(escape=True)
        self.documents = documents
        self.node_titles = {node['id']: node['title'] for node in nodes_data['nodes']}
        self.sources = {ref['id']: ref for ref in nodes_data['source_refs']}
        self.original_names = {posixpath.basename(unquote(urlsplit(ref['uri']).path))
                               for ref in [nodes_data['document'], *self.sources.values()]}
        self.source_numbers = {key: i for i, key in enumerate(self.sources, 1)}
        self.spine = {step['node_id']: step['why_next'] for step in graph['spine']}
        self.source_dir, self.output_dir = source_dir, output_dir
        self.local_details = {}
        self.context = Part()
        self.filename = ''
        self.in_link = False
        # Register the HTML render methods for the same extensions used by the AST parser.
        mistune.Markdown(renderer=self, plugins=[table, strikethrough])
        self.state = mistune.BlockState()

    def target_for_node(self, identifier):
        for name in ('architecture_analysis.md', 'design_patterns.md'):
            target = self.documents[name].targets.get('node-' + identifier)
            if target:
                return target
        return 'step-' + identifier if identifier in self.spine else 'graph'

    def text(self, text):
        if self.in_link:
            return escape(text)
        result = []
        last = 0
        for match in MARKER.finditer(text):
            result.append(escape(text[last:match.start()]))
            kind, identifier = match.groups()
            if kind == 'n':
                title = f'查看节点 · {self.node_titles[identifier]}'
                attrs = {'href': '#' + self.target_for_node(identifier), 'data-node': identifier}
                label = '节点'
            else:
                title = f'查看依据 · {self.sources[identifier]["locator"]}'
                dest = self.documents['document_map.md'].targets.get('source-' + identifier, 'sources')
                attrs = {'href': '#' + dest, 'data-source': identifier}
                label = f'依据 {self.source_numbers[identifier]}'
            attrs.update({'class': 'reader-ref', 'title': title, 'aria-label': title})
            result.append(f'<a{self.render_attrs(attrs)}>{label}</a>')
            last = match.end()
        result.append(escape(text[last:]))
        return ''.join(result)

    def navigation_group(self, token):
        """The old overview links separate Mermaid/JSON files. Combine shared destinations."""
        destinations = {}
        for index, child in enumerate(token.get('children', [])):
            if child['type'] == 'text':
                text = child['raw'].strip()
                if index == 0 and text in {'阅读入口：', '阅读入口:', 'Navigation:'}:
                    continue
                if re.fullmatch(r'[·|•\s]*', text):
                    continue
                return None
            if child['type'] != 'link':
                return None
            url = posixpath.normpath(child['attrs']['url'])
            if url not in SECTIONS and url not in GRAPH_FILES:
                return None
            route = SECTIONS.get(url, 'graph')
            label = '知识图谱' if route == 'graph' else plain(child)
            destinations.setdefault(route, label)
        if len(destinations) < 2:
            return None
        items = [f'<a href="#{route}">{escape(label)}</a>' for route, label in destinations.items()]
        return '<nav class="article-links" aria-label="相关章节">' + ' · '.join(items) + '</nav>'

    def render_token(self, token, state):
        if token['type'] == 'paragraph':
            navigation = self.navigation_group(token)
            if navigation:
                return navigation
        if token['type'] not in {'link', 'image'}:
            return super().render_token(token, state)
        self.in_link = True
        try:
            return super().render_token(token, state)
        finally:
            self.in_link = False

    def link(self, text, url, title=None):
        parts = urlsplit(url)
        filename = posixpath.normpath(unquote(parts.path))
        frag = unquote(parts.fragment)
        attrs = {'title': title}
        if not parts.scheme and not parts.netloc and (not parts.path or filename in self.documents):
            if not parts.path:
                filename = self.filename
            doc = self.documents[filename]
            if frag and frag not in doc.targets:
                if not parts.path and frag in {*SECTIONS.values(), 'graph'}:
                    return f'<a href="#{frag}">{text}</a>'
                raise ValueError(f'{self.filename}: unknown anchor {filename}#{frag}')
            target = doc.targets.get(frag, doc.route)
            attrs['href'] = '#' + self.local_details.get(target, target)
            if doc.route == 'sources' and frag.startswith('source-') and frag[7:] in self.sources:
                attrs['data-source'] = frag[7:]
        elif not parts.scheme and not parts.netloc and filename in GRAPH_FILES:
            attrs['href'] = '#graph'
        else:
            if (not parts.scheme and not parts.netloc and '/' not in filename
                    and filename.endswith(('.md', '.json', '.mmd')) and filename not in self.original_names
                    and not (self.source_dir / filename).is_file()):
                raise ValueError(f'{self.filename}: missing local document {filename}')
            href = source_href(url, self.source_dir, self.output_dir)
            if not href:
                return text
            attrs.update({'href': href, 'target': '_blank', 'rel': 'noopener noreferrer'})
            if self.context.source and self.filename == 'document_map.md':
                attrs['data-original-source'] = self.context.source
        return f'<a{self.render_attrs(attrs)}>{text}</a>'

    def image(self, text, url, title=None):
        return self.link(text or '查看原图', url, title)

    def inline_math(self, text):
        return r'<span class="math">\(' + escape(text) + r'\)</span>'

    def block_math(self, text):
        return '<span class="math" data-display="true">$$\n' + escape(text) + '\n$$</span>'

    def part(self, name, part, *, include_ids=True, after=''):
        self.filename, self.context = name, part
        cls = 'reader-step' if part.step else 'reader-topic'
        attrs = {'class': cls, 'id': part.target if include_ids else None, 'data-context-node': part.node or None}
        body = []
        if include_ids:
            for anchor in part.anchors:
                target = self.documents[name].targets[anchor]
                if target != part.target:
                    body.append(f'<span id="{escape(target)}"></span>')
        if part.heading:
            level = min(6, part.level + int(name != 'overview.md'))
            body.append(f'<h{level}>' + self.render_tokens(part.heading['children'], self.state) + f'</h{level}>')
        paragraphs = part.body
        if part.step:
            why = self.spine[part.node]
            first = paragraphs[0] if paragraphs and paragraphs[0]['type'] == 'paragraph' else None
            authored = plain(first).lstrip() if first else ''
            # Some manuscripts already put the exact transition in their first paragraph.
            # Render that entire paragraph so its formatting, additional prose and citations survive.
            labeled = re.sub(r'^[^。.!?：:\n]{1,35}[：:]\s*', '', authored, count=1)
            if first and (authored.startswith(why) or labeled.startswith(why)):
                explanation = self.render_tokens(first['children'], self.state)
                paragraphs = paragraphs[1:]
            else:
                explanation = '<strong>为什么接着学</strong> ' + escape(why)
            body.append('<p class="why-next">' + explanation + '</p>')
        body.append(self.render_tokens(paragraphs, self.state))
        body.append(after)
        if not any(body):
            return ''
        return f'<section{self.render_attrs(attrs)}>' + ''.join(body) + '</section>'

    def expansions(self, part):
        """Reuse the explicitly linked sections and the step's own detailed treatment."""
        candidates = [(name, 'node-' + part.node) for name in ('architecture_analysis.md', 'design_patterns.md')]
        for url in links(part.body):
            parts = urlsplit(url)
            name = posixpath.normpath(unquote(parts.path))
            if not parts.scheme and not parts.netloc and name in ('architecture_analysis.md', 'design_patterns.md'):
                if parts.fragment:
                    candidates.append((name, unquote(parts.fragment)))
        redirects, expansions = {}, []
        for name, anchor in dict.fromkeys(candidates):
            doc = self.documents[name]
            group = doc.detail(anchor)
            if group:
                identifier = f'expand-{part.node}-{len(expansions) + 1}'
                redirects[doc.targets[anchor]] = identifier
                label = '展开迁移条件' if name == 'design_patterns.md' else '展开设计与证据'
                inner = ''.join(self.part(name, sub, include_ids=False) for sub in group)
                expansions.append(f'<details class="step-detail" id="{identifier}"><summary>'
                                  f'{label} · {escape(group[0].title or anchor)}</summary>{inner}</details>')
        return redirects, ''.join(expansions)


def render_article(documents, nodes_data, graph, source_dir: Path, output_dir: Path) -> tuple[str, str]:
    parser = mistune.create_markdown(renderer='ast', plugins=['table', 'strikethrough', 'math', reader_syntax])
    spine_ids = {step['node_id'] for step in graph['spine']}
    docs = {name: Document(name, parser(documents[name]), spine_ids) for name in SECTIONS}
    renderer = ArticleRenderer(docs, nodes_data, graph, source_dir, output_dir)
    article, toc = [], []
    for name, doc in docs.items():
        article.append(f'<section id="{doc.route}" class="reader-section">')
        for part in doc.parts:
            extra = ''
            if part.step:
                renderer.local_details, extra = renderer.expansions(part)
                toc.append(f'<li><a href="#{part.target}">{escape(part.title)}</a></li>')
            article.append(renderer.part(name, part, after=extra))
            renderer.local_details = {}
        article.append('</section>')
    return '\n'.join(article), '\n'.join(toc)
