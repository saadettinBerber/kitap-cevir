import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from progress import Progress
from project import Project
from reader_data import Glossary, TableOfContents

GLOSSARY_TEMPLATE = ("# Sözlük\n\nAçıklama.\n\n| İngilizce Terim | Türkçe Karşılığı | Açıklama/Not |\n"
                     "|----------------|-----------------|-------------|\n"
                     "| Refactoring | Yeniden Düzenleme (Refactoring) | |\n")
PDF_OFFSET = 5
BOOK_TOTAL_PAGES = 30
LAST_TRANSLATED_PAGE = 2
SECOND_CHAPTER_START = 11
PROGRESS = {"book": {"slug": "demo", "title": "Dönüşüm", "subtitle_tr": "Alt başlık", "author": "Yazar"},
            "book_pdf": "book.pdf", "pdf_offset": PDF_OFFSET, "book_total_pages": BOOK_TOTAL_PAGES,
            "last_translated_page": LAST_TRANSLATED_PAGE,
            "chapters": [{"num": 1, "en": "One", "tr": "Bir", "start": 1},
                         {"num": 2, "en": "Two", "tr": "İki", "start": SECOND_CHAPTER_START}],
            "pages": {"1": {"pdf_page": 6, "chapter": 1, "title_en": "T", "title_tr": "B",
                            "section_en": "S", "section_tr": "K"},
                      "2": {"blank": True, "pdf_page": 7}}}


class _ProjectTestCase(unittest.TestCase):
    """PROGRESS ve GLOSSARY_TEMPLATE'le kurulmuş bir kitap projesi; testi yoktur."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        open(os.path.join(root, "progress.json"), "w", encoding="utf-8").write(json.dumps(PROGRESS))
        open(os.path.join(root, "glossary.md"), "w", encoding="utf-8").write(GLOSSARY_TEMPLATE)
        self.project = Project(root)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _js_payload(path, prefix):
        raw = open(path, encoding="utf-8").read().strip()
        return json.loads(raw[len(prefix):-1])


class TableOfContentsTest(_ProjectTestCase):
    def setUp(self):
        super().setUp()
        TableOfContents(self.project, Progress(PROGRESS)).write()
        self.toc = self._js_payload(self.project.toc_js(), "window.TOC = ")

    def test_book_info_uses_the_reader_field_names(self):
        self.assertEqual(self.toc["book"], {"slug": "demo", "title": "Dönüşüm", "subtitle": "",
                                            "subtitleTr": "Alt başlık", "author": "Yazar", "series": ""})

    def test_page_counts_come_from_the_progress_record(self):
        self.assertEqual((self.toc["bookTotalPages"], self.toc["pdfOffset"], self.toc["lastTranslatedPage"]),
                         (BOOK_TOTAL_PAGES, PDF_OFFSET, LAST_TRANSLATED_PAGE))

    def test_chapter_ends_before_the_next_one_starts(self):
        self.assertEqual([chapter["end"] for chapter in self.toc["chapters"]],
                         [SECOND_CHAPTER_START - 1, BOOK_TOTAL_PAGES])

    def test_translated_page_carries_its_titles_and_chapter(self):
        self.assertEqual(self.toc["pages"]["1"], {"title": {"en": "T", "tr": "B"}, "section": {"en": "S", "tr": "K"},
                                                  "chapter": 1})

    def test_blank_page_is_only_marked(self):
        self.assertEqual(self.toc["pages"]["2"], {"blank": True})


class ReaderScriptTest(_ProjectTestCase):
    def test_script_defines_one_global_with_readable_json(self):
        TableOfContents(self.project, Progress(PROGRESS)).write()
        with open(self.project.toc_js(), encoding="utf-8") as handle:
            self.assertTrue(handle.read().startswith('window.TOC = {\n  "book": {\n    "slug": "demo",\n    "title": "Dönüşüm"'))

    def test_script_ends_the_statement(self):
        TableOfContents(self.project, Progress(PROGRESS)).write()
        with open(self.project.toc_js(), encoding="utf-8") as handle:
            self.assertTrue(handle.read().endswith("\n};\n"))


class GlossaryTest(_ProjectTestCase):
    def test_glossary_terms_are_added_sorted_and_deduplicated(self):
        added = Glossary(self.project).add([
            {"en": "Abstraction", "tr": "Soyutlama (Abstraction)", "note": ""},
            {"en": "refactoring", "tr": "tekrar", "note": "kopya"}])
        self.assertEqual(added, 1)
        terms = Glossary(self.project).terms
        self.assertEqual([t["en"] for t in terms], ["Abstraction", "Refactoring"])

    def test_glossary_adds_a_repeated_new_term_once(self):
        added = Glossary(self.project).add([{"en": "Zeta Term", "tr": "Zeta"}, {"en": "zeta term", "tr": "zeta"}])
        self.assertEqual(added, 1)
        self.assertEqual([t["tr"] for t in Glossary(self.project).terms], ["Yeniden Düzenleme (Refactoring)", "Zeta"])

    def test_glossary_skips_terms_without_english(self):
        self.assertEqual(Glossary(self.project).add([{"en": "", "tr": "boş"}, {"tr": "yok"}]), 0)
        self.assertEqual(len(Glossary(self.project).terms), 1)

    def test_glossary_js_is_generated(self):
        Glossary(self.project).write_js()
        entries = self._js_payload(self.project.glossary_js(), "window.GLOSSARY = ")
        self.assertEqual(entries[0]["en"], "Refactoring")


if __name__ == "__main__":
    unittest.main()
