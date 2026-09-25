import unittest

import _paths  # noqa: F401
from progress import Progress

PDF_OFFSET = 19
FIRST_CHAPTER_START = 3
SECOND_CHAPTER_START = 10
SECTION_PAGE = 4


class PageLocationTest(unittest.TestCase):
    CHAPTERS = [{"num": 1, "en": "One", "tr": "Bir", "start": FIRST_CHAPTER_START},
                {"num": 2, "en": "Two", "tr": "İki", "start": SECOND_CHAPTER_START}]

    def setUp(self):
        self.progress = Progress({"pdf_offset": PDF_OFFSET, "chapters": self.CHAPTERS,
                                  "pages": {str(SECTION_PAGE): {"section_en": "Intro", "section_tr": "Giriş"}}})

    def test_pdf_page_adds_the_offset(self):
        self.assertEqual(self.progress.pdf_page(1), 1 + PDF_OFFSET)

    def test_chapter_starts_on_its_first_page(self):
        self.assertEqual(self.progress.chapter_of(SECOND_CHAPTER_START)["num"], 2)

    def test_page_before_a_chapter_start_is_in_the_previous_chapter(self):
        self.assertEqual(self.progress.chapter_of(SECOND_CHAPTER_START - 1)["num"], 1)

    def test_page_before_the_first_chapter_has_no_chapter(self):
        self.assertEqual(self.progress.chapter_of(FIRST_CHAPTER_START - 1), {"num": 0, "en": "", "tr": ""})

    def test_section_comes_from_the_recorded_page(self):
        self.assertEqual(self.progress.section_of(SECTION_PAGE), {"en": "Intro", "tr": "Giriş"})

    def test_unrecorded_page_has_an_empty_section(self):
        self.assertEqual(self.progress.section_of(SECTION_PAGE + 1), {"en": "", "tr": ""})


class PageRecordTest(unittest.TestCase):
    OFFSET = 2
    LAST_PAGE = 10
    LAST_TRANSLATED = 7
    NEXT = LAST_TRANSLATED + 1

    def setUp(self):
        self.progress = Progress({"pdf_offset": self.OFFSET, "book_total_pages": self.LAST_PAGE,
                                  "last_translated_page": self.LAST_TRANSLATED, "pages": {}})

    def _recorded(self, page):
        return self.progress.as_json()["pages"][str(page)]

    def test_next_pages_follow_the_last_translated_page(self):
        self.assertEqual(self.progress.next_pages(2), [self.NEXT, self.NEXT + 1])

    def test_next_pages_stop_at_the_end_of_the_book(self):
        self.assertEqual(self.progress.next_pages(self.LAST_PAGE), list(range(self.NEXT, self.LAST_PAGE + 1)))

    def test_finished_book_has_no_next_pages(self):
        self.progress.mark_blank(self.LAST_PAGE)
        self.assertEqual(self.progress.next_pages(1), [])

    def test_blank_page_is_recorded_with_its_pdf_page(self):
        self.progress.mark_blank(self.NEXT)
        self.assertEqual(self._recorded(self.NEXT), {"blank": True, "pdf_page": self.NEXT + self.OFFSET})

    def test_blank_page_moves_the_last_translated_page(self):
        self.progress.mark_blank(self.NEXT)
        self.assertEqual(self.progress.next_pages(1), [self.NEXT + 1])

    def test_retranslating_an_earlier_page_keeps_the_last_page(self):
        earlier = self.LAST_TRANSLATED - 1
        self.progress.record_translation({"page": earlier, "pdf_page": earlier + self.OFFSET})
        self.assertEqual(self.progress.next_pages(1), [self.NEXT])

    def test_translation_record_carries_toc_fields(self):
        self.progress.record_translation({"page": self.NEXT, "pdf_page": self.NEXT + self.OFFSET,
                                          "chapter": {"num": 2}, "title": {"en": "T", "tr": "B"},
                                          "section": {"en": "S", "tr": "K"}})
        self.assertEqual(self._recorded(self.NEXT), {"pdf_page": self.NEXT + self.OFFSET, "chapter": 2,
                                                     "title_en": "T", "title_tr": "B",
                                                     "section_en": "S", "section_tr": "K"})

    def test_pages_per_run_defaults_to_one(self):
        self.assertEqual(self.progress.pages_per_run(), 1)


class JsonFormTest(unittest.TestCase):
    RECORD = {"pages": {"3": {"pdf_page": 22}}}

    def test_json_form_is_the_whole_record(self):
        self.assertEqual(Progress(self.RECORD).as_json(), self.RECORD)

    def test_changing_the_json_form_leaves_the_record_intact(self):
        progress = Progress({"pages": {}})
        progress.as_json()["pages"].update(self.RECORD["pages"])
        self.assertEqual(progress.translated_pages(), [])


class TranslatedPagesTest(unittest.TestCase):
    """Çevrilmiş sayfaların tek kaynağı progress.json'daki kayıttır; sayfa numaraları kayıttaki
    anahtarlardır."""

    def test_recorded_pages_are_listed_in_order(self):
        progress = Progress({"pages": {"12": {}, "3": {}}})
        self.assertEqual(progress.translated_pages(), [3, 12])

    def test_blank_page_is_not_translated(self):
        progress = Progress({"pages": {"3": {}, "4": {"blank": True}}})
        self.assertEqual(progress.translated_pages(), [3])

    def test_no_record_means_no_translated_pages(self):
        self.assertEqual(Progress({"pages": {}}).translated_pages(), [])


if __name__ == "__main__":
    unittest.main()
