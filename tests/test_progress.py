import unittest

import _paths  # noqa: F401
from progress import Progress


class PageLocationTest(unittest.TestCase):
    CHAPTERS = [{"num": 1, "en": "One", "tr": "Bir", "start": 3}, {"num": 2, "en": "Two", "tr": "İki", "start": 10}]

    def setUp(self):
        self.progress = Progress({"pdf_offset": 19, "chapters": self.CHAPTERS,
                                  "pages": {"4": {"section_en": "Intro", "section_tr": "Giriş"}}})

    def test_pdf_page_adds_the_offset(self):
        self.assertEqual(self.progress.pdf_page(1), 20)

    def test_chapter_starts_on_its_first_page(self):
        self.assertEqual(self.progress.chapter_of(10)["num"], 2)
        self.assertEqual(self.progress.chapter_of(9)["num"], 1)

    def test_page_before_the_first_chapter_has_no_chapter(self):
        self.assertEqual(self.progress.chapter_of(2), {"num": 0, "en": "", "tr": ""})

    def test_section_comes_from_the_recorded_page(self):
        self.assertEqual(self.progress.section_of(4), {"en": "Intro", "tr": "Giriş"})

    def test_unrecorded_page_has_an_empty_section(self):
        self.assertEqual(self.progress.section_of(5), {"en": "", "tr": ""})



class PageRecordTest(unittest.TestCase):
    def setUp(self):
        self.progress = Progress({"pdf_offset": 2, "book_total_pages": 10, "last_translated_page": 7, "pages": {}})

    def test_next_pages_follow_the_last_translated_page(self):
        self.assertEqual(self.progress.next_pages(2), [8, 9])

    def test_next_pages_stop_at_the_end_of_the_book(self):
        self.assertEqual(self.progress.next_pages(5), [8, 9, 10])

    def test_finished_book_has_no_next_pages(self):
        self.progress.mark_blank(10)
        self.assertEqual(self.progress.next_pages(3), [])

    def test_blank_page_is_recorded_with_its_pdf_page(self):
        self.progress.mark_blank(8)
        self.assertEqual(self.progress.as_json()["pages"]["8"], {"blank": True, "pdf_page": 10})
        self.assertEqual(self.progress.as_json()["last_translated_page"], 8)

    def test_retranslating_an_earlier_page_keeps_the_last_page(self):
        self.progress.record_translation({"page": 3, "pdf_page": 5})
        self.assertEqual(self.progress.as_json()["last_translated_page"], 7)

    def test_translation_record_carries_toc_fields(self):
        self.progress.record_translation({"page": 8, "pdf_page": 10, "chapter": {"num": 2},
                                          "title": {"en": "T", "tr": "B"}, "section": {"en": "S", "tr": "K"}})
        self.assertEqual(self.progress.as_json()["pages"]["8"], {"pdf_page": 10, "chapter": 2, "title_en": "T",
                                                            "title_tr": "B", "section_en": "S", "section_tr": "K"})

    def test_pages_per_run_defaults_to_one(self):
        self.assertEqual(self.progress.pages_per_run(), 1)


class JsonFormTest(unittest.TestCase):
    def test_json_form_is_the_whole_record(self):
        self.assertEqual(Progress({"pages": {"3": {"pdf_page": 22}}}).as_json(), {"pages": {"3": {"pdf_page": 22}}})

    def test_changing_the_json_form_leaves_the_record_intact(self):
        progress = Progress({"pages": {}})
        progress.as_json()["pages"]["3"] = {"pdf_page": 22}
        self.assertEqual(progress.translated_pages(), [])


class TranslatedPagesTest(unittest.TestCase):
    """Çevrilmiş sayfaların tek kaynağı progress.json'daki kayıttır."""

    def test_recorded_pages_are_listed_in_order(self):
        progress = Progress({"pages": {"12": {"pdf_page": 31}, "3": {"pdf_page": 22}}})
        self.assertEqual(progress.translated_pages(), [3, 12])

    def test_blank_page_is_not_translated(self):
        progress = Progress({"pages": {"3": {"pdf_page": 22}, "4": {"blank": True, "pdf_page": 23}}})
        self.assertEqual(progress.translated_pages(), [3])

    def test_no_record_means_no_translated_pages(self):
        self.assertEqual(Progress({"pages": {}}).translated_pages(), [])


if __name__ == "__main__":
    unittest.main()
