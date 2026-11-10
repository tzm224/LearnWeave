"""Regressions for taking five independent Markdown documents into one offline HTML."""
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from model import read_bundle
from reader_article import SECTIONS, render_article, source_href


class Links(HTMLParser):
    def __init__(self, article):
        super().__init__()
        self.tags = []
        self.ids = []
        self.links = []
        self.feed(article)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append(tag)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs)


class ArticleTests(unittest.TestCase):
    def setUp(self):
        self.directory = SCRIPTS.parent / 'examples/versioned-cache/expected'
        self.docs = {name: (self.directory / name).read_text(encoding='utf-8') for name in SECTIONS}
        self.nodes, self.graph = read_bundle(self.directory)

    def render(self):
        return render_article(self.docs, self.nodes, self.graph, self.directory, self.directory.parent / 'reader')

    def test_original_links_and_namespaced_anchors(self):
        article, toc = self.render()
        page = Links(article + toc)
        self.assertEqual(len(page.ids), len(set(page.ids)))
        for link in page.links:
            if link['href'].startswith('#'):
                self.assertIn(link['href'][1:], {*page.ids, 'graph'})
        original = next(link for link in page.links if link.get('data-original-source') == 's_trace')
        self.assertEqual(original['href'], '../source.md')
        self.assertIn('analysis-node-validate_at_commit', page.ids)
        self.assertIn('patterns-node-validate_at_commit', page.ids)
        step = article.split('id="step-publish_guard"', 1)[1].split('id="step-old_fill_rejected"', 1)[0]
        self.assertIn(self.graph['spine'][4]['why_next'], step)
        self.assertIn('替代设计', step.split('<details', 1)[1])
        self.assertIn('拆开动作会发生什么', step)
        self.assertIn('data-source="s_trace"', step)
        nav = article.split('class="article-links"', 1)[1].split('</nav>', 1)[0]
        self.assertEqual(nav.count('href="#graph"'), 1)
        self.assertEqual([link['href'] for link in Links(toc).links],
                         ['#step-' + step['node_id'] for step in self.graph['spine']])

    def test_existing_rationale_keeps_extra_explanation_and_sources(self):
        directory = SCRIPTS.parent / 'examples/mergeable-summary/expected'
        docs = {name: (directory / name).read_text(encoding='utf-8') for name in SECTIONS}
        data, graph = read_bundle(directory)
        rationale = graph['spine'][0]['why_next']
        docs['knowledge_spine.md'] = docs['knowledge_spine.md'].replace(
            rationale, rationale + ' 参见第一节。 [s:setting]', 1)
        article, _ = render_article(docs, data, graph, directory, directory)
        step = article.split('id="step-problem"', 1)[1].split('id="step-contract"', 1)[0]
        self.assertEqual(step.count(rationale), 1)
        lead = step.split('class="why-next"', 1)[1].split('</p>', 1)[0]
        self.assertIn('参见第一节', lead)
        self.assertIn('data-source="setting"', lead)

    def test_rich_text_math_and_code_remain_distinct(self):
        self.docs['overview.md'] += r"""

## Expressions

> **strong** and *emphasis*, $x^2$ and \(\sqrt{y}\).

$$
y < x
$$

| key | value |
| --- | --- |
| estimate | 2 |

```py
message = '[s:s_trace] $x$'
```
"""
        article, _ = self.render()
        section = article.split('id="overview-heading-expressions"', 1)[1].split('id="spine"', 1)[0]
        for tag in ('table', 'blockquote', 'code', 'strong', 'em'):
            self.assertIn(tag, Links(section).tags)
        self.assertIn(r'\(\sqrt{y}\)', section)
        self.assertIn('data-display="true">$$\ny &lt; x\n$$', section)
        self.assertEqual(section.count('class="math"'), 3)
        self.assertNotIn('data-source=', section)
        self.assertIn('[s:s_trace] $x$', section)

    def test_raw_html_schemes_and_image_autoload(self):
        self.docs['overview.md'] += '''
<script>attack()</script>

<img src="x" onerror="attack()">

[raw](javascript:attack) [encoded](java%73cript:attack)
![source figure](https://example.org/original.png)
'''
        article, _ = self.render()
        output = Links(article)
        self.assertNotIn('script', output.tags)
        self.assertNotIn('img', output.tags)
        self.assertFalse(any('script:attack' in link['href'] for link in output.links))
        self.assertIn('https://example.org/original.png', {link['href'] for link in output.links})

    def test_broken_internal_links_and_duplicate_anchors(self):
        for fragment, error in [
            ('[nowhere](architecture_analysis.md#missing)', 'unknown anchor'),
            ('[typo](knowledeg_spine.md)', 'missing local document'),
            ('<a id="source-one"></a>\n\ntext\n\n<a id="source-one"></a>', 'duplicate anchor'),
        ]:
            with self.subTest(fragment=fragment):
                self.docs['overview.md'] += '\n\n' + fragment
                with self.assertRaisesRegex(ValueError, error):
                    self.render()
                self.docs['overview.md'] = self.docs['overview.md'].removesuffix('\n\n' + fragment)

    def test_original_link_rebasing_and_allowed_schemes(self):
        self.assertEqual(source_href('../paper%20notes.pdf?q=1#page=3', Path('/in/drafts'), Path('/out/view')),
                         '../../in/paper%20notes.pdf?q=1#page=3')
        self.assertEqual(source_href('https://example.org/study#proof', Path('/a'), Path('/b')),
                         'https://example.org/study#proof')
        for uri in ('javascript:evil', 'data:text/html,hi', 'java%73cript:evil', '//host/asset', r'\\host\asset'):
            with self.subTest(uri=uri):
                self.assertIsNone(source_href(uri, Path('/a'), Path('/b')))


if __name__ == '__main__':
    unittest.main()
