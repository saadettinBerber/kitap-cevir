import os
import tempfile
import unittest

from pdf_fakes import FAKE_PNG, FakePdfPage, span, stroke
from extraction.equations.math_scan import MathLine, MathScanner, placeholder
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


def _is_math(span):
    return span.font == MATH_FONT


def _math(text, x0, x1):
    return span(text, (x0, 90, x1, 102), MATH_FONT, 11)


def _prose(text, x0, x1):
    return span(text, (x0, 90, x1, 102))


def _neighbours(*spans):
    [inline_run] = MathLine(spans, _is_math).inline_runs()
    return inline_run.before, inline_run.after


class MathLineTest(unittest.TestCase):
    """Satır içi denklemin yeri, cümledeki komşu kelimeleriyle bulunur."""

    def test_neighbours_are_the_nearest_words_on_both_sides(self):
        self.assertEqual(_neighbours(_prose("Goal: find ", 72, 126), _math("x", 126, 132), _prose(" to minimize", 132, 200)),
                         ("find", "to"))

    def test_equation_opening_the_line_has_no_word_before(self):
        self.assertEqual(_neighbours(_math("x", 72, 78), _prose(" grows fast", 78, 140)), ("", "grows"))

    def test_equation_closing_the_line_has_no_word_after(self):
        self.assertEqual(_neighbours(_prose("it minimizes ", 72, 140), _math("x", 140, 146)), ("minimizes", ""))

    def test_blank_neighbour_gives_no_word(self):
        self.assertEqual(_neighbours(_prose(" ", 72, 76), _math("x", 76, 82)), ("", ""))

    def test_line_all_in_math_font_is_a_display_line_without_inline_runs(self):
        line = MathLine((_math("E = mc2", 72, 115),), _is_math)
        self.assertTrue(line.is_display())
        self.assertEqual(line.inline_runs(), [])

    def test_line_mixing_prose_and_math_is_not_a_display_line(self):
        self.assertFalse(MathLine((_prose("find ", 72, 100), _math("x", 100, 106)), _is_math).is_display())


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
