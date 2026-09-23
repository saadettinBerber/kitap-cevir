import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from finalize_page import finalize, missing_translations, read_page_js
from project import Project

GLOSSARY = ("# S\n\n| İngilizce Terim | Türkçe Karşılığı | Açıklama/Not |\n"
            "|----------------|-----------------|-------------|\n")
PROGRESS = {"book": {"slug": "demo", "title": "Demo"}, "book_pdf": "book.pdf", "pdf_offset": 5,
            "book_total_pages": 30, "last_translated_page": 0,
            "chapters": [{"num": 1, "en": "One", "tr": "Bir", "start": 1}], "pages": {}}
DOCUMENT = {"id": "page-3", "page": 3, "pdf_page": 8,
            "chapter": {"num": 1, "en": "One", "tr": "Bir"},
            "section": {"en": "Sec", "tr": "Kesit"}, "title": {"en": "T", "tr": "B"},
            "blocks": [{"type": "heading", "level": 1, "en": "H", "tr": "B"},
                       {"type": "para", "sentences": [{"en": "A.", "tr": "A."}, {"en": "B.", "tr": ""}]},
                       {"type": "code", "lang": "java", "code": "int x;"}],
            "concepts": [], "context": {"prev_tail": "gizli"},
            "glossary_new": [{"en": "Heading", "tr": "Başlık (Heading)", "note": ""}]}


class FinalizeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        open(os.path.join(root, "progress.json"), "w", encoding="utf-8").write(json.dumps(PROGRESS))
        open(os.path.join(root, "glossary.md"), "w", encoding="utf-8").write(GLOSSARY)
        self.out = os.path.join(root, "page-3.json")
        open(self.out, "w", encoding="utf-8").write(json.dumps(DOCUMENT, ensure_ascii=False))
        self.project = Project(root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_counts_missing_translations(self):
        self.assertEqual(missing_translations(DOCUMENT), 1)

    def test_finalize_writes_page_progress_and_glossary(self):
        result = finalize(self.project, self.out)
        page_js = open(result["page_js"], encoding="utf-8").read()
        self.assertTrue(page_js.startswith("window.PAGE("))
        self.assertNotIn("gizli", page_js)
        progress = self.project.load_progress()
        self.assertEqual(progress["last_translated_page"], 3)
        self.assertEqual(progress["pages"]["3"]["title_tr"], "B")
        self.assertEqual(result["terms"], 1)
        self.assertIn("Heading", open(self.project.glossary_md, encoding="utf-8").read())
        self.assertTrue(os.path.isfile(self.project.toc_js))

    def test_finalize_reports_card_problems(self):
        result = finalize(self.project, self.out)
        self.assertEqual(result["card_problems"], ["kart sayısı 0 (2-4 olmalı)"])

    def test_page_js_round_trips(self):
        result = finalize(self.project, self.out)
        self.assertEqual(read_page_js(result["page_js"])["title"], {"en": "T", "tr": "B"})


if __name__ == "__main__":
    unittest.main()
