import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from project import Project
from reader_data import Glossary, TableOfContents

GLOSSARY_TEMPLATE = ("# Sözlük\n\nAçıklama.\n\n| İngilizce Terim | Türkçe Karşılığı | Açıklama/Not |\n"
                     "|----------------|-----------------|-------------|\n"
                     "| Refactoring | Yeniden Düzenleme (Refactoring) | |\n")
PROGRESS = {"book": {"slug": "demo", "title": "Demo", "author": "Yazar"}, "book_pdf": "book.pdf",
            "pdf_offset": 5, "book_total_pages": 30, "last_translated_page": 2,
            "chapters": [{"num": 1, "en": "One", "tr": "Bir", "start": 1},
                         {"num": 2, "en": "Two", "tr": "İki", "start": 11}],
            "pages": {"1": {"pdf_page": 6, "chapter": 1, "title_en": "T", "title_tr": "B",
                            "section_en": "S", "section_tr": "K"},
                      "2": {"blank": True, "pdf_page": 7}}}


class ReaderDataTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        open(os.path.join(root, "progress.json"), "w", encoding="utf-8").write(json.dumps(PROGRESS))
        open(os.path.join(root, "glossary.md"), "w", encoding="utf-8").write(GLOSSARY_TEMPLATE)
        self.project = Project(root)

    def tearDown(self):
        self.tmp.cleanup()

    def _js_payload(self, path, prefix):
        raw = open(path, encoding="utf-8").read().strip()
        return json.loads(raw[len(prefix):-1])

    def test_toc_contains_book_and_chapter_ends(self):
        TableOfContents(self.project, PROGRESS).write()
        toc = self._js_payload(self.project.toc_js, "window.TOC = ")
        self.assertEqual(toc["book"]["slug"], "demo")
        self.assertEqual([c["end"] for c in toc["chapters"]], [10, 30])
        self.assertTrue(toc["pages"]["2"]["blank"])

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
        entries = self._js_payload(self.project.glossary_js, "window.GLOSSARY = ")
        self.assertEqual(entries[0]["en"], "Refactoring")


if __name__ == "__main__":
    unittest.main()
