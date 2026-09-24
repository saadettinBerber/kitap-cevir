import os
import tempfile
import unittest

from pdf_fakes import FAKE_PNG, FakePdfPage, span, stroke
from extraction.equations.math_scan import MathScanner, placeholder
from extraction.settings import with_defaults

MATH_FONT = "Helvetica-Oblique"
SETTINGS = with_defaults({"math_font_prefix": MATH_FONT})


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
        result = MathScanner(with_defaults({"math_font_prefix": "NoSuchFont"}), self.images).scan(_page())
        self.assertEqual(result, {"display": [], "inline": []})

    def test_empty_prefix_means_no_math_font(self):
        result = MathScanner(with_defaults({"math_font_prefix": ""}), self.images).scan(_page())
        self.assertEqual(result, {"display": [], "inline": []})


def _display_with_mixed_line():
    """İki tam denklem satırı ve aralarında denklem fontunda olmayan '…' taşıyan
    bir satır (ai-engineering PDF 245): ayrı satır denkleminin parçası."""
    top = (span("P(x1, x2)", (72, 50, 150, 62), MATH_FONT, 11),)
    mixed = (span("P(x", (72, 58, 90, 68), MATH_FONT, 11), span("1", (90, 62, 94, 69), MATH_FONT, 7),
             span("\u2026", (121, 58, 130, 68)),
             span(",xn)", (131, 58, 160, 68), MATH_FONT, 11))
    bottom = (span("= (1/P)", (72, 66, 130, 78), MATH_FONT, 11),)
    return FakePdfPage(lines=[top, mixed, bottom])


class DisplayRegionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.images = os.path.join(self.tmp.name, "images")
        self.result = MathScanner(SETTINGS, self.images).scan(_display_with_mixed_line())

    def tearDown(self):
        self.tmp.cleanup()

    def test_mixed_line_inside_a_display_equation_has_no_inline_items(self):
        self.assertEqual(self.result["inline"], [])

    def test_only_the_display_equation_is_cropped(self):
        self.assertEqual(len(self.result["display"]), 1)
        self.assertEqual(os.listdir(self.images), [self.result["display"][0]["block"]["src"]])


def _inline_on(line):
    with tempfile.TemporaryDirectory() as images:
        [item] = MathScanner(SETTINGS, images).scan(FakePdfPage(lines=[line]))["inline"]
    return item


class NeighbourWordsTest(unittest.TestCase):
    """Satır içi denklemin yeri, cümledeki komşu kelimeleriyle bulunur."""

    def test_equation_opening_the_line_has_no_word_before(self):
        item = _inline_on((span("x", (72, 90, 78, 102), MATH_FONT, 11), span(" grows fast", (78, 90, 140, 102))))
        self.assertEqual((item["before"], item["after"]), ("", "grows"))

    def test_equation_closing_the_line_has_no_word_after(self):
        item = _inline_on((span("it minimizes ", (72, 90, 140, 102)), span("x", (140, 90, 146, 102), MATH_FONT, 11)))
        self.assertEqual((item["before"], item["after"]), ("minimizes", ""))

    def test_blank_neighbour_gives_no_word(self):
        item = _inline_on((span(" ", (72, 90, 76, 102)), span("x", (76, 90, 82, 102), MATH_FONT, 11)))
        self.assertEqual((item["before"], item["after"]), ("", ""))


def _fraction_under_caption():
    """Kesir çizgisinin hemen üstünde denklem başlığı; altında uzak bir gövde satırı."""
    caption = (span("Equation 3-3. Abstractness", (72, 182, 200, 192)),)
    numerator = (span("A = ma", (87, 196, 125, 206)),)
    denominator = (span("mc", (106, 210, 125, 220)),)
    prose = (span("In the equation, ma represents abstract elements.", (72, 260, 432, 272)),)
    return FakePdfPage(lines=[caption, numerator, denominator, prose], shapes=[stroke(106, 208, 125, 208.6)])


class GeometryCaptionTest(unittest.TestCase):
    def test_caption_above_the_fraction_stays_out_of_the_equation(self):
        with tempfile.TemporaryDirectory() as images:
            result = MathScanner(with_defaults({"math_geometry": True}), images).scan(_fraction_under_caption())
        [region] = result["display"]
        self.assertEqual(region["block"]["text"], "A = ma mc")


if __name__ == "__main__":
    unittest.main()
