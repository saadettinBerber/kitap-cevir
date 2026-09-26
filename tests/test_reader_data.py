import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from json_file import write_json
from progress import Progress
from project import Project
from reader_data import Glossary, ReaderData

GLOSSARY_PREAMBLE = ("# Sözlük\n\nAçıklama.\n\n| İngilizce Terim | Türkçe Karşılığı | Açıklama/Not |\n"
                     "|----------------|-----------------|-------------|\n")
GLOSSARY_TEMPLATE = GLOSSARY_PREAMBLE + "| Refactoring | Yeniden Düzenleme (Refactoring) | |\n"
READABLE_TOC_START = 'window.TOC = {\n  "book": {\n    "slug": "demo",\n    "title": "Dönüşüm"'
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


def _write_text(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class _ProjectTestCase(unittest.TestCase):
    """PROGRESS ve GLOSSARY_TEMPLATE'le kurulmuş bir kitap projesi; testi yoktur."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        write_json(os.path.join(root, "progress.json"), PROGRESS)
        _write_text(os.path.join(root, "glossary.md"), GLOSSARY_TEMPLATE)
        self.project = Project(root)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _js_payload(path, prefix):
        with open(path, encoding="utf-8") as script:
            raw = script.read().strip()
        return json.loads(raw[len(prefix):-1])


class TableOfContentsTest(_ProjectTestCase):
    def setUp(self):
        super().setUp()
        ReaderData(self.project).write_toc(Progress(PROGRESS))
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
        ReaderData(self.project).write_toc(Progress(PROGRESS))
        with open(self.project.toc_js(), encoding="utf-8") as handle:
            self.assertTrue(handle.read().startswith(READABLE_TOC_START))

    def test_script_ends_the_statement(self):
        ReaderData(self.project).write_toc(Progress(PROGRESS))
        with open(self.project.toc_js(), encoding="utf-8") as handle:
            self.assertTrue(handle.read().endswith("\n};\n"))


class GlossaryTest(_ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.glossary = Glossary(self.project.glossary_md())

    def _reread_entries(self):
        return Glossary(self.project.glossary_md()).entries()

    def test_known_term_is_not_new_whatever_its_case(self):
        new_terms = self.glossary.unknown([{"en": "Abstraction", "tr": "Soyutlama"}, {"en": "refactoring", "tr": "x"}])
        self.assertEqual([term["en"] for term in new_terms], ["Abstraction"])

    def test_repeated_new_term_is_new_once(self):
        new_terms = self.glossary.unknown([{"en": "Zeta Term", "tr": "Zeta"}, {"en": "zeta term", "tr": "zeta"}])
        self.assertEqual(new_terms, [{"en": "Zeta Term", "tr": "Zeta"}])

    def test_term_without_english_is_not_new(self):
        self.assertEqual(self.glossary.unknown([{"en": "", "tr": "boş"}, {"tr": "yok"}]), [])

    def test_added_terms_are_read_back_alphabetically(self):
        self.glossary.add([{"en": "Zeta", "tr": "Zeta"}, {"en": "Abstraction", "tr": "Soyutlama"}])
        self.assertEqual([entry["en"] for entry in self._reread_entries()], ["Abstraction", "Refactoring", "Zeta"])

    def test_adding_a_known_term_keeps_the_old_translation(self):
        self.glossary.add([{"en": "refactoring", "tr": "tekrar"}])
        self.assertEqual([entry["tr"] for entry in self._reread_entries()], ["Yeniden Düzenleme (Refactoring)"])

    def test_markdown_keeps_the_preamble_and_lists_rows_alphabetically(self):
        self.glossary.add([{"en": "Abstraction", "tr": "Soyutlama", "note": "Not"}])
        with open(self.project.glossary_md(), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), GLOSSARY_PREAMBLE + "| Abstraction | Soyutlama | Not |\n"
                             "| Refactoring | Yeniden Düzenleme (Refactoring) |  |\n")


class ReaderGlossaryTest(_ProjectTestCase):
    def test_reader_glossary_is_alphabetical(self):
        with open(self.project.glossary_md(), "a", encoding="utf-8") as handle:
            handle.write("| Coupling | Bağlılık | |\n| Abstraction | Soyutlama | |\n")
        ReaderData(self.project).write_glossary(Glossary(self.project.glossary_md()))
        entries = self._js_payload(self.project.glossary_js(), "window.GLOSSARY = ")
        self.assertEqual([entry["en"] for entry in entries], ["Abstraction", "Coupling", "Refactoring"])


if __name__ == "__main__":
    unittest.main()
