import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from math_scan import placeholder, scan_math

MATH_FONT = "Helvetica-Oblique"
SETTINGS = {"math_font_prefix": MATH_FONT}
BASELINE = 100


def _make_pdf(path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text(fitz.Point(72, 60), "E = mc2", fontsize=11, fontname="helvetica-oblique")
    page.insert_text(fitz.Point(72, BASELINE), "Goal: find ", fontsize=11, fontname="helvetica")
    page.insert_text(fitz.Point(126, BASELINE), "x", fontsize=11, fontname="helvetica-oblique")
    page.insert_text(fitz.Point(133, BASELINE - 4), "2", fontsize=7, fontname="helvetica-oblique")
    page.insert_text(fitz.Point(140, BASELINE), " to minimize", fontsize=11, fontname="helvetica")
    page.insert_text(fitz.Point(72, 140), "Body text without math.", fontsize=11, fontname="helvetica")
    document.save(path)
    document.close()


class MathScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "m.pdf")
        self.images = os.path.join(self.tmp.name, "images")
        _make_pdf(self.pdf)
        self.result = scan_math(self.pdf, 1, SETTINGS, self.images)

    def tearDown(self):
        self.tmp.cleanup()

    def test_display_equation_becomes_math_block_with_png(self):
        display = self.result["display"]
        self.assertEqual(len(display), 1)
        block = display[0]["block"]
        self.assertEqual(block["type"], "math")
        self.assertEqual(block["text"], "E = mc2")
        self.assertEqual(block["latex"], "")
        self.assertTrue(os.path.isfile(os.path.join(self.images, block["src"])))

    def test_inline_equation_with_superscript_gets_placeholder_image(self):
        inline = self.result["inline"]
        self.assertEqual(len(inline), 1)
        item = inline[0]
        self.assertEqual(item["kind"], "image")
        self.assertEqual((item["before"], item["after"]), ("find", "to"))
        self.assertTrue(os.path.isfile(os.path.join(self.images, item["src"])))
        self.assertEqual(placeholder(item["id"]), f"⟦{item['id']}⟧")

    def test_page_without_math_font_yields_nothing(self):
        result = scan_math(self.pdf, 1, {"math_font_prefix": "NoSuchFont"}, self.images)
        self.assertEqual(result, {"display": [], "inline": []})


if __name__ == "__main__":
    unittest.main()
