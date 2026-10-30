"""Small behavioral tests for package resolution, page order and note filtering."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from pypdf import PdfWriter

SCRIPT = Path(__file__).resolve().parents[1] / 'prepare_source.py'
spec = importlib.util.spec_from_file_location('prepare_source', SCRIPT)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)

P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL='http://schemas.openxmlformats.org/package/2006/relationships'


def fixture(path, broken=False):
    with ZipFile(path, 'w') as z:
        z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst><p:sldId id="999" r:id="rIdSecond"/><p:sldId id="256" r:id="rIdFirst"/></p:sldIdLst></p:presentation>')
        target = '../../../escape.xml' if broken else 'slides/not-lexical-a.xml'
        z.writestr('ppt/_rels/presentation.xml.rels',f'<Relationships xmlns="{REL}"><Relationship Id="rIdFirst" Type="{R}/slide" Target="{target}"/><Relationship Id="rIdSecond" Type="{R}/slide" Target="slides/z.xml"/></Relationships>')
        for name, label, hidden in [('not-lexical-a.xml','A',False),('z.xml','B',True)]:
            z.writestr('ppt/slides/'+name,f'<p:sld xmlns:p="{P}" xmlns:a="{A}" show="{0 if hidden else 1}"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Slide {label}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
            z.writestr('ppt/slides/_rels/'+name+'.rels',f'<Relationships xmlns="{REL}"><Relationship Id="notes" Type="{R}/notesSlide" Target="../notesSlides/note{label}.xml"/></Relationships>')
            z.writestr(f'ppt/notesSlides/note{label}.xml',f'<p:notes xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>Notes {label}</a:t></a:r></a:p></p:txBody></p:sp><p:sp><p:nvSpPr><p:nvPr><p:ph type="ftr"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>NOT TEACHING</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>')


class SourceTests(unittest.TestCase):
    def test_presentation_order_and_notes_not_filename_order(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.pptx'
            fixture(path)
            pages, title, warnings, hidden=prep.extract_pptx(path)
            self.assertEqual([p['text'] for p in pages],['Slide B','Slide A'])
            self.assertEqual([p['notes'] for p in pages],['Notes B','Notes A'])
            self.assertEqual([p['page'] for p in pages],[1,2])
            self.assertEqual(hidden,['ppt/slides/z.xml'])
            self.assertIn('Hidden slide',pages[0]['warnings'][0])
            self.assertEqual([p['printed_page'] for p in pages],[None,None])

    def test_relationship_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'broken.pptx'
            fixture(path,broken=True)
            with self.assertRaises(prep.PreparationError):
                prep.extract_pptx(path)

    def test_package_root_absolute_path_is_valid(self):
        self.assertEqual(prep.resolve_target('ppt/slides/slide1.xml','/ppt/notesSlides/n.xml'),'ppt/notesSlides/n.xml')

    def test_external_or_encoded_escape_is_rejected(self):
        for target in ['https://example.com/a.xml','file:///secret','%2E%2E/%2E%2E/%2E%2E/a.xml']:
            with self.subTest(target=target),self.assertRaises(prep.PreparationError):
                prep.resolve_target('ppt/slides/s.xml',target)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            source=base/'fixture.pptx'
            fixture(source)
            output=base/'output'
            output.mkdir()
            (output/'important.txt').write_text('keep')
            with self.assertRaises(prep.PreparationError):
                prep.prepare(source,output)
            self.assertEqual((output/'important.txt').read_text(),'keep')

    def test_blank_pdf_is_retained_with_visual_read_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'blank.pdf'
            writer=PdfWriter()
            writer.add_blank_page(width=200,height=100)
            writer.write(path)
            pages,_,_=prep.extract_pdf(path)
            self.assertEqual(len(pages),1)
            self.assertEqual(pages[0]['text'],'')
            self.assertTrue(pages[0]['warnings'])
            self.assertIsNone(pages[0]['printed_page'])

    def test_render_copy_preserves_namespaces_and_original(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'hidden.pptx'
            output=Path(folder)/'visible.pptx'
            original=b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:a14="urn:unused-but-referenced" mc:Ignorable="a14" show="0"><p:cSld/></p:sld>'
            with ZipFile(source,'w') as archive:
                archive.writestr('ppt/slides/s.xml',original)
            prep.rendering_copy(source,output,['ppt/slides/s.xml'])
            with ZipFile(source) as archive:
                self.assertEqual(archive.read('ppt/slides/s.xml'),original)
            with ZipFile(output) as archive:
                self.assertEqual(archive.read('ppt/slides/s.xml'),original.replace(b'show="0"',b'show="1"'))

    def test_incomplete_image_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(prep.PreparationError):
                prep.install_images([], [{'page':1}], Path(folder)/'pages')


if __name__ == '__main__':
    unittest.main()
