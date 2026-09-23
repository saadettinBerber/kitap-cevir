import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from code_lines import page_lines
from layout_scan import CodeFont

SETTINGS = {"code_font_prefix": "Courier", "code_max_font_size": 12}
BASELINE = 100


def _make_pdf(path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text(fitz.Point(72, BASELINE), "(3 x 10", fontsize=11, fontname="courier")
    page.insert_text(fitz.Point(120, BASELINE - 5), "23", fontsize=7, fontname="courier")
    page.insert_text(fitz.Point(132, BASELINE), ") =", fontsize=11, fontname="courier")
    page.insert_text(fitz.Point(200, BASELINE), "236 days", fontsize=11, fontname="courier")
    page.insert_text(fitz.Point(72, 140), "W", fontsize=11, fontname="courier")
    page.insert_text(fitz.Point(84, 140), "is the weight matrix.", fontsize=11, fontname="helvetica")
    document.save(path)
    document.close()


class CodeLinesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pdf = os.path.join(self.tmp.name, "c.pdf")
        _make_pdf(pdf)
        document = fitz.open(pdf)
        self.lines = page_lines(document[0], CodeFont(SETTINGS))
        document.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_superscript_and_split_fragments_form_one_code_line(self):
        code = [line for line in self.lines if line.is_code]
        self.assertEqual(len(code), 1)
        self.assertTrue(code[0].text.startswith("(3 x 10^23) ="))
        self.assertTrue(code[0].text.endswith("236 days"))

    def test_single_letter_before_prose_is_not_a_code_line(self):
        prose = [line for line in self.lines if not line.is_code]
        texts = [line.text for line in prose]
        self.assertTrue(any("W" in text for text in texts), texts)


if __name__ == "__main__":
    unittest.main()
