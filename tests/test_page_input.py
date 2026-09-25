import unittest

import _paths  # noqa: F401
from page_input import PageInputBuilder
from progress import Progress

PAGE = 5
PDF_OFFSET = 2
IMAGE_DIR = "/proje/_work/in/page-5_images"
PARA = {"type": "para", "sentences": [{"en": "Text."}]}
EQUATION = {"src": "eq-1.png", "text": "x", "latex": ""}
CONTEXT = {"prev_tail": "önceki", "next_head": "sonraki"}
CHAPTER = {"num": 1, "en": "One", "tr": "Bir", "start": 1}
PREVIOUS_SECTION = {"section_en": "Layers", "section_tr": "Katmanlar"}


class FakeBookPdf:
    """BookPdf gibi; her sayfanın çıkarımı aynı blokları ve verilen koşu başlığını verir."""

    def __init__(self, running_header):
        self._running_header = running_header
        self._image_dirs = []

    def extract(self, pdf_page, image_dir):
        self._image_dirs.append((pdf_page, image_dir))
        return {"blocks": [PARA], "math": [EQUATION], "context": CONTEXT, "running_header": self._running_header}

    def hyphen_fixes(self, pdf_page):
        return {f"PDF {pdf_page}": "onarım"}

    def image_dirs(self):
        return list(self._image_dirs)


def _progress():
    return Progress({"pdf_offset": PDF_OFFSET, "chapters": [CHAPTER], "pages": {str(PAGE - 1): PREVIOUS_SECTION}})


def _input(running_header=None):
    return PageInputBuilder(_progress(), FakeBookPdf(running_header)).build(PAGE, IMAGE_DIR)


class PageInputTest(unittest.TestCase):
    def test_input_names_the_page_and_its_pdf_page(self):
        document = _input()
        self.assertEqual((document["id"], document["page"], document["pdf_page"]),
                         ("page-5", PAGE, PAGE + PDF_OFFSET))

    def test_input_carries_the_chapter(self):
        self.assertEqual(_input()["chapter"], {"num": 1, "en": "One", "tr": "Bir"})

    def test_extracted_content_goes_into_the_input(self):
        document = _input()
        self.assertEqual((document["blocks"], document["math"], document["context"]), ([PARA], [EQUATION], CONTEXT))

    def test_translation_fields_start_empty(self):
        document = _input()
        self.assertEqual((document["title"], document["concepts"], document["glossary_new"]),
                         ({"en": "", "tr": ""}, [], []))

    def test_images_are_written_to_the_given_folder(self):
        book_pdf = FakeBookPdf(None)
        PageInputBuilder(_progress(), book_pdf).build(PAGE, IMAGE_DIR)
        self.assertEqual(book_pdf.image_dirs(), [(PAGE + PDF_OFFSET, IMAGE_DIR)])

    def test_hyphen_fixes_come_from_the_pdf(self):
        builder = PageInputBuilder(_progress(), FakeBookPdf(None))
        self.assertEqual(builder.hyphen_fixes(PAGE + PDF_OFFSET), {"PDF 7": "onarım"})


class SectionTest(unittest.TestCase):
    """Koşu başlığı kesiti söyler; bölüm açılışında başlık yoktur, bölüm adlı başlıkta kesit sürer."""

    def test_page_without_running_header_opens_a_chapter_without_section(self):
        self.assertEqual(_input(None)["section"], {"en": "", "tr": ""})

    def test_running_header_names_the_section(self):
        self.assertEqual(_input({"is_chapter": False, "text": "Styles"})["section"], {"en": "Styles", "tr": ""})

    def test_chapter_header_continues_the_previous_section(self):
        self.assertEqual(_input({"is_chapter": True, "text": "Chapter 1"})["section"],
                         {"en": "Layers", "tr": "Katmanlar"})

    def test_empty_header_continues_the_previous_section(self):
        self.assertEqual(_input({"is_chapter": False, "text": ""})["section"], {"en": "Layers", "tr": "Katmanlar"})


if __name__ == "__main__":
    unittest.main()
