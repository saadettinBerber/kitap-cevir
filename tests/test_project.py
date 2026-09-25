import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from progress import Progress
from project import Project, ProjectNotFound, find_root


class FindRootTest(unittest.TestCase):
    def test_walks_up_to_progress_json(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, "progress.json"), "w").write("{}")
            nested = os.path.join(root, "a", "b")
            os.makedirs(nested)
            self.assertEqual(find_root(nested), os.path.realpath(root) if os.path.realpath(root) == root else root)

    def test_raises_when_missing(self):
        with tempfile.TemporaryDirectory() as root:
            os.environ.pop("KITAP_ROOT", None)
            with self.assertRaises(ProjectNotFound):
                find_root(root)

    def test_env_override_wins(self):
        with tempfile.TemporaryDirectory() as root:
            os.environ["KITAP_ROOT"] = root
            try:
                self.assertEqual(find_root("/"), root)
            finally:
                del os.environ["KITAP_ROOT"]


class PdfPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Project(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _configure_pdf(self, book_pdf):
        self.project.save_progress(Progress({"book_pdf": book_pdf}))

    def test_absolute_pdf_path_is_kept(self):
        self._configure_pdf("/x/y.pdf")
        self.assertEqual(self.project.pdf_path(), "/x/y.pdf")

    def test_relative_pdf_path_is_inside_the_project(self):
        self._configure_pdf("kaynak/kitap.pdf")
        self.assertEqual(self.project.relative_to_root(self.project.pdf_path()), "kaynak/kitap.pdf")


class LayoutTest(unittest.TestCase):
    """Okuyucu, ajanlar ve kullanıcı dosyaları bu yollarda arar; yollar proje köküne göredir."""

    PAGE = 7

    def setUp(self):
        self.project = Project("/kitap")

    def _relative(self, path):
        return self.project.relative_to_root(path)

    def test_reader_data_files(self):
        self.assertEqual([self._relative(path) for path in (self.project.toc_js(), self.project.glossary_js())],
                         ["data/toc.js", "data/glossary.js"])

    def test_glossary_source(self):
        self.assertEqual(self._relative(self.project.glossary_md()), "glossary.md")

    def test_translated_page_files(self):
        paths = (self.project.page_js(self.PAGE), self.project.page_images(self.PAGE))
        self.assertEqual([self._relative(path) for path in paths], ["data/pages/page-7.js", "data/pages/page-7_images"])

    def test_translator_work_files(self):
        paths = (self.project.work_input(self.PAGE), self.project.work_images(self.PAGE),
                 self.project.work_output(self.PAGE))
        self.assertEqual([self._relative(path) for path in paths],
                         ["_work/in/page-7.json", "_work/in/page-7_images", "_work/out/page-7.json"])

    def test_card_work_files(self):
        self.assertEqual(self._relative(self.project.work_cards_file("in", self.PAGE)), "_work/cards/in/page-7.json")

    def test_migration_work_files(self):
        self.assertEqual(self._relative(self.project.work_migration_file("pending", self.PAGE)),
                         "_work/migrate/pending-7.json")

    def test_epub_file(self):
        self.assertEqual(self._relative(self.project.epub_file("demo")), "dist/demo.epub")


class ProgressFileTest(unittest.TestCase):
    PAGE = 3
    RECORD = {"pages": {str(PAGE): {"pdf_page": 22, "section_en": "Shelf", "section_tr": "Kitaplık"}}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Project(self.tmp.name).save_progress(Progress(self.RECORD))

    def tearDown(self):
        self.tmp.cleanup()

    def test_saved_progress_reads_back(self):
        progress = Project(self.tmp.name).load_progress()
        self.assertEqual(progress.section_of(self.PAGE), {"en": "Shelf", "tr": "Kitaplık"})

    def test_saved_progress_keeps_turkish_letters_and_ends_with_a_newline(self):
        with open(os.path.join(self.tmp.name, "progress.json"), encoding="utf-8") as handle:
            self.assertTrue(handle.read().endswith('"Kitaplık"\n    }\n  }\n}\n'))


if __name__ == "__main__":
    unittest.main()
