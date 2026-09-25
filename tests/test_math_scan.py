"""Denklem fontundaki denklemler: ayrı satır denklemi math bloğu, cümle içindeki
denklem yer tutuculu öğe olur; PNG'ler görsel klasörüne kırpılır."""
import os
import tempfile
import unittest

from pdf_fakes import FAKE_PNG, FakePdfPage, span
from extraction.equations.math_scan import MathScanner, placeholder
from extraction.settings import with_defaults

MATH_FONT = "Helvetica-Oblique"
MATH_SIZE = 11
SUPERSCRIPT_SIZE = 7
SETTINGS = with_defaults({"math_font_prefix": MATH_FONT})


def _math(text, box):
    return span(text, box, MATH_FONT, MATH_SIZE)


def _page():
    """Ayrı satırda bir denklem, cümle içinde üst simgeli bir denklem ve düz metin."""
    display = (_math("E = mc2", (72, 50, 115, 62)),)
    inline = (span("Goal: find ", (72, 90, 126, 102)), _math("x", (126, 90, 132, 102)),
              span("2", (133, 88, 137, 95), MATH_FONT, SUPERSCRIPT_SIZE), span(" to minimize", (140, 90, 200, 102)))
    prose = (span("Body text without math.", (72, 130, 200, 142)),)
    return FakePdfPage(lines=[display, inline, prose])


def _display_with_mixed_line():
    """İki tam denklem satırı ve aralarında denklem fontunda olmayan '…' taşıyan
    bir satır (ai-engineering PDF 245): ayrı satır denkleminin parçası."""
    top = (_math("P(x1, x2)", (72, 50, 150, 62)),)
    mixed = (_math("P(x", (72, 58, 90, 68)), span("1", (90, 62, 94, 69), MATH_FONT, SUPERSCRIPT_SIZE),
             span("…", (121, 58, 130, 68)), _math(",xn)", (131, 58, 160, 68)))
    bottom = (_math("= (1/P)", (72, 66, 130, 78)),)
    return FakePdfPage(lines=[top, mixed, bottom])


class ScanCase(unittest.TestCase):
    """Her test kendi geçici görsel klasörüne tarar."""

    def setUp(self):
        images = tempfile.TemporaryDirectory()
        self.addCleanup(images.cleanup)
        self.images = os.path.join(images.name, "images")

    def _scan(self, page, settings=SETTINGS):
        return MathScanner(settings, page, self.images).scan()

    def _png(self, name):
        with open(os.path.join(self.images, name), "rb") as png:
            return png.read()


class DisplayEquationTest(ScanCase):
    def setUp(self):
        super().setUp()
        [self.region] = self._scan(_page())["display"]

    def test_display_equation_becomes_a_math_block(self):
        self.assertEqual(self.region["block"]["type"], "math")

    def test_block_carries_the_text_layer(self):
        self.assertEqual(self.region["block"]["text"], "E = mc2")

    def test_latex_is_left_to_the_translator(self):
        self.assertEqual(self.region["block"]["latex"], "")

    def test_png_is_cropped_into_the_image_dir(self):
        png = self._png(self.region["block"]["src"])
        self.assertEqual(png, FAKE_PNG)


class InlineEquationTest(ScanCase):
    def setUp(self):
        super().setUp()
        [self.item] = self._scan(_page())["inline"]

    def test_equation_with_superscript_is_an_image(self):
        self.assertEqual(self.item["kind"], "image")

    def test_item_knows_its_neighbour_words(self):
        self.assertEqual((self.item["before"], self.item["after"]), ("find", "to"))

    def test_png_is_cropped_into_the_image_dir(self):
        png = self._png(self.item["src"])
        self.assertEqual(png, FAKE_PNG)

    def test_single_size_short_run_becomes_plain_text(self):
        line = (span("area ", (72, 90, 100, 102)), _math("πr", (100, 90, 112, 102)), span(" grows", (112, 90, 150, 102)))
        [item] = self._scan(FakePdfPage(lines=[line]))["inline"]
        self.assertEqual((item["kind"], item["text"]), ("text", "πr"))


class MathFontTest(ScanCase):
    def test_page_without_math_font_yields_nothing(self):
        result = self._scan(_page(), with_defaults({"math_font_prefix": "NoSuchFont"}))
        self.assertEqual(result, {"display": [], "inline": []})

    def test_empty_prefix_means_no_math_font(self):
        result = self._scan(_page(), with_defaults({"math_font_prefix": ""}))
        self.assertEqual(result, {"display": [], "inline": []})


class DisplayRegionTest(ScanCase):
    def setUp(self):
        super().setUp()
        self.result = self._scan(_display_with_mixed_line())

    def test_mixed_line_inside_a_display_equation_has_no_inline_items(self):
        self.assertEqual(self.result["inline"], [])

    def test_only_the_display_equation_is_cropped(self):
        self.assertEqual(os.listdir(self.images), [self.result["display"][0]["block"]["src"]])


class PlaceholderTest(unittest.TestCase):
    def test_placeholder_wraps_the_equation_id(self):
        self.assertEqual(placeholder("eq-1"), "⟦eq-1⟧")


if __name__ == "__main__":
    unittest.main()
