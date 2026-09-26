import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from finalize_page import IncompletePage, PageFinalizer
from page_document import PageDocument
from project import Project
from translated_pages import TranslatedPages

PAGE = 3
GLOSSARY = ("# S\n\n| İngilizce Terim | Türkçe Karşılığı | Açıklama/Not |\n"
            "|----------------|-----------------|-------------|\n")
PROGRESS = {"book": {"slug": "demo", "title": "Demo"}, "book_pdf": "book.pdf", "pdf_offset": 5,
            "book_total_pages": 30, "last_translated_page": 0,
            "chapters": [{"num": 1, "en": "One", "tr": "Bir", "start": 1}], "pages": {}}
DOCUMENT = {"id": "page-3", "page": PAGE, "pdf_page": 8,
            "chapter": {"num": 1, "en": "One", "tr": "Bir"},
            "section": {"en": "Sec", "tr": "Kesit"}, "title": {"en": "T", "tr": "B"},
            "blocks": [{"type": "heading", "level": 1, "en": "H", "tr": "B"},
                       {"type": "para", "sentences": [{"en": "A.", "tr": "A."}, {"en": "B.", "tr": ""}]},
                       {"type": "code", "lang": "java", "code": "int x;"}],
            "concepts": [], "context": {"prev_tail": "gizli"},
            "glossary_new": [{"en": "Heading", "tr": "Başlık (Heading)", "note": ""}]}
FIGURE = {"type": "image", "src": "fig.png"}
WITH_FIGURE = {**DOCUMENT, "blocks": DOCUMENT["blocks"] + [FIGURE]}
CARD = {"id": "tek", "kind": "explain", "title": {"en": "T", "tr": "B"},
        "summary": {"en": "S", "tr": "Ö"}, "tip": {"en": "T", "tr": "İ"}}


class _FinalizeTestCase(unittest.TestCase):
    """PROGRESS ve boş sözlükle kurulmuş bir proje; çevirmen çıktısı _finalize ile işlenir. Testi yoktur."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._write_text("progress.json", json.dumps(PROGRESS))
        self._write_text("glossary.md", GLOSSARY)
        self.project = Project(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_text(self, name, text):
        path = os.path.join(self.tmp.name, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def _finalize(self, document):
        out = self._write_text("_work/out/page-3.json", json.dumps(document, ensure_ascii=False))
        return PageFinalizer.for_project(self.project).finalize(out)

    @staticmethod
    def _read_text(path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()


class PageFileTest(_FinalizeTestCase):
    def test_page_file_is_a_reader_script(self):
        page_js = self._read_text(self._finalize(DOCUMENT)["page_js"])
        self.assertTrue(page_js.startswith("window.PAGE("))

    def test_agent_only_fields_stay_out_of_the_page_file(self):
        page_js = self._read_text(self._finalize(DOCUMENT)["page_js"])
        self.assertNotIn("gizli", page_js)

    def test_page_file_reads_back(self):
        self._finalize(DOCUMENT)
        self.assertEqual(TranslatedPages(self.project).get(PAGE).data["title"], {"en": "T", "tr": "B"})

    def test_missing_required_field_is_refused(self):
        document = {key: value for key, value in DOCUMENT.items() if key != "blocks"}
        with self.assertRaises(IncompletePage):
            self._finalize(document)


class ProgressRecordTest(_FinalizeTestCase):
    def test_page_becomes_the_last_translated_page(self):
        self._finalize(DOCUMENT)
        progress = Project(self.tmp.name).load_progress()
        self.assertEqual(progress.next_pages(1), [PAGE + 1])

    def test_page_titles_are_recorded(self):
        self._finalize(DOCUMENT)
        record = json.loads(self._read_text(os.path.join(self.tmp.name, "progress.json")))
        self.assertEqual(record["pages"][str(PAGE)]["title_tr"], "B")


class ReaderDataUpdateTest(_FinalizeTestCase):
    def test_new_glossary_term_is_counted(self):
        self.assertEqual(self._finalize(DOCUMENT)["terms"], 1)

    def test_page_without_new_terms_adds_none(self):
        without_terms = {key: value for key, value in DOCUMENT.items() if key != "glossary_new"}
        self.assertEqual(self._finalize(without_terms)["terms"], 0)

    def test_new_glossary_term_is_written(self):
        self._finalize(DOCUMENT)
        self.assertIn("| Heading | Başlık (Heading) |", self._read_text(self.project.glossary_md()))

    def test_reader_table_of_contents_is_rebuilt(self):
        self._finalize(DOCUMENT)
        self.assertIn(f'"{PAGE}": {{', self._read_text(self.project.toc_js()))


class PageImagesTest(_FinalizeTestCase):
    def _put_in_work_folder(self, name):
        self._write_text(f"_work/in/page-3_images/{name}", "png")

    def test_image_in_the_work_folder_is_copied_next_to_the_page(self):
        self._put_in_work_folder(FIGURE["src"])
        self._finalize(WITH_FIGURE)
        self.assertEqual(os.listdir(self.project.page_images(PAGE)), [FIGURE["src"]])

    def test_copied_images_are_counted(self):
        self._put_in_work_folder(FIGURE["src"])
        self.assertEqual(self._finalize(WITH_FIGURE)["images"], 1)

    def test_image_missing_from_the_work_folder_is_skipped(self):
        self.assertEqual(self._finalize(WITH_FIGURE)["images"], 0)

    def test_page_naming_images_gets_an_image_folder_even_if_none_is_copied(self):
        self._finalize(WITH_FIGURE)
        self.assertEqual(os.listdir(self.project.page_images(PAGE)), [])

    def test_page_without_images_gets_no_image_folder(self):
        self._finalize(DOCUMENT)
        self.assertFalse(os.path.exists(self.project.page_images(PAGE)))


class CardCheckTest(_FinalizeTestCase):
    def test_counts_missing_translations(self):
        self.assertEqual(PageDocument(DOCUMENT).missing_translations(), 1)

    def test_page_without_cards_waits_for_the_card_step(self):
        result = self._finalize(DOCUMENT)
        self.assertEqual((result["cards_pending"], result["card_problems"]), (True, []))

    def test_finalize_reports_card_problems(self):
        result = self._finalize({**DOCUMENT, "concepts": [CARD]})
        self.assertEqual((result["cards_pending"], result["card_problems"]), (False, ["kart sayısı 1 (2-4 olmalı)"]))


if __name__ == "__main__":
    unittest.main()
