"""Check the single-file delivery, recovery and legacy conversion contracts."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from build_reader import build, extract, read_reader
from model import MARKDOWN_FILES, read_bundle
from validate import validate_directory


class ReaderBuildTests(unittest.TestCase):
    def setUp(self):
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        self.root = Path(cache.name).resolve()
        self.examples = SCRIPTS.parent / 'examples'

    def test_both_legacy_examples_round_trip_to_exact_content(self):
        for case in ('versioned-cache', 'mergeable-summary'):
            with self.subTest(case=case):
                project = self.root / case
                drafts = project / 'work'
                shutil.copytree(self.examples / case / 'expected', drafts)
                shutil.copy2(self.examples / case / 'source.md', project / 'source.md')
                site, _ = build(drafts, project / 'reader')
                self.assertEqual(list(site.parent.iterdir()), [site])
                published = site.read_bytes()
                metadata, _ = read_reader(site)
                for source in metadata['nodes']['source_refs']:
                    href = metadata['source_links'][source['id']]
                    self.assertEqual((site.parent / unquote(href)).resolve(), project / 'source.md')

                recovered, _ = extract(site, project / 'deep' / 'recovered')
                for name in MARKDOWN_FILES:
                    self.assertEqual((recovered / name).read_bytes(), (drafts / name).read_bytes())
                self.assertEqual(read_bundle(recovered), read_bundle(drafts))
                self.assertEqual(validate_directory(recovered)[0], [])
                copied_site, _ = build(recovered, site.parent)
                self.assertEqual(copied_site.read_bytes(), published)

                # A follow-up can change the prose while retaining the IDs and source locations.
                with (recovered / 'overview.md').open('a', encoding='utf-8') as record:
                    record.write('\n\nUpdated analysis from a follow-up.\n')
                build(recovered, site.parent)
                updated, _ = read_reader(site)
                self.assertIn('Updated analysis', updated['documents']['overview.md'])
                self.assertEqual(updated['graph'], metadata['graph'])

    def test_script_termination_and_template_tokens_round_trip_as_data(self):
        drafts = self.root / 'work'
        shutil.copytree(self.examples / 'versioned-cache' / 'expected', drafts)
        (drafts / 'knowledge_graph.mmd').unlink()
        attack = '</script><script>globalThis.injected = true;</script> __PAYLOAD__ & __SCRIPT__'
        with (drafts / 'overview.md').open('a', encoding='utf-8') as record:
            record.write(f'\n\n`{attack}`\n')
        metadata = json.loads((drafts / 'knowledge_nodes.json').read_text(encoding='utf-8'))
        metadata['document']['title'] = attack
        (drafts / 'knowledge_nodes.json').write_text(json.dumps(metadata), encoding='utf-8')
        entry, _ = build(drafts, self.root / 'reader')
        self.assertNotIn(attack, entry.read_text(encoding='utf-8'))
        embedded, _ = read_reader(entry)
        self.assertEqual(embedded['nodes']['document']['title'], attack)
        self.assertIn(attack, embedded['documents']['overview.md'])

    def test_failed_recovery_and_rebuild_leave_previous_files_intact(self):
        drafts = self.examples / 'versioned-cache' / 'expected'
        entry, _ = build(drafts, self.root / 'reader')
        original = entry.read_bytes()
        with self.assertRaisesRegex(ValueError, 'different document'):
            build(self.examples / 'mergeable-summary' / 'expected', entry.parent)
        self.assertEqual(entry.read_bytes(), original)
        blocked = self.root / 'occupied'
        blocked.mkdir()
        private = blocked / 'user.txt'
        private.write_text('keep', encoding='utf-8')
        for fn, source in ((build, drafts), (extract, entry)):
            with self.subTest(action=fn.__name__):
                with self.assertRaises(ValueError):
                    fn(source, blocked)
                self.assertEqual(list(blocked.iterdir()), [private])
                self.assertEqual(private.read_text(encoding='utf-8'), 'keep')

    def test_validation_rejects_broken_navigation_duplicate_anchors_and_bad_embedded_versions(self):
        entry, _ = build(self.examples / 'mergeable-summary' / 'expected', self.root / 'reader')
        original = entry.read_text(encoding='utf-8')
        for markup, reason in (
            (original.replace('</body>', '<a href="#absent-target">go</a></body>'), 'Unresolved HTML anchor'),
            (original.replace('</body>', '<div id="overview"></div></body>'), 'Duplicate HTML anchor'),
            (original.replace('"format_version":1', '"format_version":2'), 'Unsupported HTML reader'),
            (original.replace('</body>', '<script src="https://example.test/x"></script></body>'), 'not embedded'),
        ):
            with self.subTest(reason=reason):
                entry.write_text(markup, encoding='utf-8')
                recovered = self.root / 'should-not-exist'
                with self.assertRaisesRegex(ValueError, reason):
                    extract(entry, recovered)
                self.assertFalse(recovered.exists())


if __name__ == '__main__':
    unittest.main()
