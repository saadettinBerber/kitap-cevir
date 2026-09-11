import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from project import Project
from toc_builder import add_glossary_terms, read_glossary, write_glossary_js, write_toc

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


class TocBuilderTest(unittest.TestCase):
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
        write_toc(self.project, PROGRESS)
        toc = self._js_payload(self.project.toc_js, "window.TOC = ")
        self.assertEqual(toc["book"]["slug"], "demo")
        self.assertEqual([c["end"] for c in toc["chapters"]], [10, 30])
        self.assertTrue(toc["pages"]["2"]["blank"])

    def test_glossary_terms_are_added_sorted_and_deduplicated(self):
        added = add_glossary_terms(self.project, [
            {"en": "Abstraction", "tr": "Soyutlama (Abstraction)", "note": ""},
            {"en": "refactoring", "tr": "tekrar", "note": "kopya"}])
        self.assertEqual(added, 1)
        _, terms = read_glossary(self.project)
        self.assertEqual([t["en"] for t in terms], ["Abstraction", "Refactoring"])

    def test_glossary_js_is_generated(self):
        write_glossary_js(self.project)
        entries = self._js_payload(self.project.glossary_js, "window.GLOSSARY = ")
        self.assertEqual(entries[0]["en"], "Refactoring")


if __name__ == "__main__":
    unittest.main()
