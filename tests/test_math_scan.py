import os
import tempfile
import unittest

from pdf_fakes import FAKE_PNG, FakePdfPage, span
from extraction.equations.math_scan import MathScanner, placeholder

MATH_FONT = "Helvetica-Oblique"
SETTINGS = {"math_font_prefix": MATH_FONT}


def _page():
    """Ayrı satırda bir denklem, cümle içinde üst simgeli bir denklem ve düz metin."""
    display = (span("E = mc2", (72, 50, 115, 62), MATH_FONT, 11),)
    inline = (span("Goal: find ", (72, 90, 126, 102)), span("x", (126, 90, 132, 102), MATH_FONT, 11),
              span("2", (133, 88, 137, 95), MATH_FONT, 7), span(" to minimize", (140, 90, 200, 102)))
    prose = (span("Body text without math.", (72, 130, 200, 142)),)
    return FakePdfPage(lines=[display, inline, prose])


class MathScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.images = os.path.join(self.tmp.name, "images")
        self.result = MathScanner(SETTINGS, self.images).scan(_page())

    def tearDown(self):
        self.tmp.cleanup()

    def _png(self, name):
        with open(os.path.join(self.images, name), "rb") as png:
            return png.read()

    def test_display_equation_becomes_math_block_with_png(self):
        display = self.result["display"]
        self.assertEqual(len(display), 1)
        block = display[0]["block"]
        self.assertEqual(block["type"], "math")
        self.assertEqual(block["text"], "E = mc2")
        self.assertEqual(block["latex"], "")
        self.assertEqual(self._png(block["src"]), FAKE_PNG)

    def test_inline_equation_with_superscript_gets_placeholder_image(self):
        inline = self.result["inline"]
        self.assertEqual(len(inline), 1)
        item = inline[0]
        self.assertEqual(item["kind"], "image")
        self.assertEqual((item["before"], item["after"]), ("find", "to"))
        self.assertEqual(self._png(item["src"]), FAKE_PNG)
        self.assertEqual(placeholder(item["id"]), f"⟦{item['id']}⟧")

    def test_single_size_short_run_becomes_plain_text(self):
        line = (span("area ", (72, 90, 100, 102)), span("πr", (100, 90, 112, 102), MATH_FONT, 11),
                span(" grows", (112, 90, 150, 102)))
        [item] = MathScanner(SETTINGS, self.images).scan(FakePdfPage(lines=[line]))["inline"]
        self.assertEqual((item["kind"], item["text"]), ("text", "πr"))

    def test_page_without_math_font_yields_nothing(self):
        result = MathScanner({"math_font_prefix": "NoSuchFont"}, self.images).scan(_page())
        self.assertEqual(result, {"display": [], "inline": []})

    def test_empty_prefix_means_no_math_font(self):
        result = MathScanner({"math_font_prefix": ""}, self.images).scan(_page())
        self.assertEqual(result, {"display": [], "inline": []})


if __name__ == "__main__":
    unittest.main()
