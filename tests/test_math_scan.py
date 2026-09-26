"""Denklem fontundaki denklemler: ayrı satır denklemi math bloğu, cümle içindeki
denklem yer tutuculu öğe olur; PNG'ler görsel klasörüne kırpılır."""
import os
import tempfile
import unittest
from unittest import mock

from pdf_fakes import FAKE_PNG, FakePdfPage, span, stroke
from extraction.equations.math_scan import CROP_DPI, CROP_PADDING, LINE_MERGE_RATIO, MathScanner, placeholder
from extraction.pdf.geometry import Box
from extraction.settings import with_defaults

MATH_FONT = "Helvetica-Oblique"
MATH_SIZE = 11
SUPERSCRIPT_SIZE = 7
SETTINGS = with_defaults({"math_font_prefix": MATH_FONT})
DISPLAY_BOX = (72, 50, 115, 62)
DISPLAY_TOP, DISPLAY_BOTTOM = DISPLAY_BOX[1], DISPLAY_BOX[3]
LINE_LEFT, LINE_RIGHT = 72, 115
LINE_HEIGHT = 10
STEP = 0.1


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


def _display_line():
    return (_math("E = mc2", DISPLAY_BOX),)


def _display_page(*lines):
    """Ayrı satır denklemi ve ardından gelen satırlar."""
    return FakePdfPage(lines=[_display_line(), *lines])


def _display_line_at(top):
    return (_math("c = d", (LINE_LEFT, top, LINE_RIGHT, top + LINE_HEIGHT)),)


def _inline_centred_at(center_y):
    """Cümle içinde, denklem parçasının ortası center_y'de olan satır."""
    top, bottom = center_y - LINE_HEIGHT / 2, center_y + LINE_HEIGHT / 2
    return span("see ", (LINE_LEFT, top, 90, bottom)), _math("x", (90, top, 96, bottom))


def _fraction_above_display():
    """Üstte düz metinle dizilmiş bir kesir (geometriyle bulunur), altta denklem fontunda bir satır."""
    numerator = (span("A =", (87, 191, 102, 205)), span("ma", (106, 191, 120, 205)))
    denominator = (span("mc", (106, 208, 119, 222)),)
    prose = (span("In the equation, ma represents abstract elements.", (72, 249, 303, 263)),)
    lines = [numerator, denominator, prose, (_math("E = mc2", (72, 300, 115, 312)),)]
    return FakePdfPage(lines=lines, shapes=[stroke(106, 208, 125, 208)])


def _superscripted(base, mark):
    """Üst simgeli denklem: iki punto, basit sayılmaz."""
    return _math(base, (0, 90, 6, 102)), span(mark, (6, 88, 10, 95), MATH_FONT, SUPERSCRIPT_SIZE)


def _images_around_a_symbol():
    """Cümlede iki görsel denklem, aralarında düz metne çevrilen bir sembol; üstte ayrı satır denklemi."""
    inline = (span("see ", (0, 90, 1, 102)), *_superscripted("x", "2"), span(" and ", (0, 90, 1, 102)),
              _math("πr", (0, 90, 1, 102)), span(" then ", (0, 90, 1, 102)), *_superscripted("y", "3"))
    return _display_page(inline)


class ScanCase(unittest.TestCase):
    """Her test kendi geçici görsel klasörüne tarar."""

    def setUp(self):
        images = tempfile.TemporaryDirectory()
        self.addCleanup(images.cleanup)
        self.images = os.path.join(images.name, "images")

    def _scan(self, page, settings=SETTINGS):
        return MathScanner(settings).scan(page, self.images)

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


class DisplayBlockTest(ScanCase):
    def test_block_holds_only_the_image_text_and_latex(self):
        [region] = self._scan(_display_page())["display"]
        self.assertEqual(region["block"], {"type": "math", "src": "eq-1.png", "text": "E = mc2", "latex": ""})

    def test_region_spans_the_equation_line(self):
        [region] = self._scan(_display_page())["display"]
        self.assertEqual((region["y0"], region["y1"]), (DISPLAY_TOP, DISPLAY_BOTTOM))

    def test_block_text_has_single_spaces(self):
        page = FakePdfPage(lines=[(_math("E =", DISPLAY_BOX), _math(" mc2", DISPLAY_BOX))])
        [region] = self._scan(page)["display"]
        self.assertEqual(region["block"]["text"], "E = mc2")

    def test_crop_is_padded_around_the_equation(self):
        page = _display_page()
        with mock.patch.object(page, "png", wraps=page.png) as png:
            self._scan(page)
        self.assertEqual(png.call_args_list, [mock.call(Box(*DISPLAY_BOX).expanded(CROP_PADDING), CROP_DPI)])


class AdjacentLinesTest(ScanCase):
    """Ardışık denklem satırları, aradaki boşluk satır yüksekliğinin bir oranını
    aşmıyorsa tek denklemdir."""

    def test_line_at_the_merge_gap_joins_the_equation(self):
        page = _display_page(_display_line_at(DISPLAY_BOTTOM + LINE_HEIGHT * LINE_MERGE_RATIO))
        self.assertEqual(len(self._scan(page)["display"]), 1)

    def test_line_past_the_merge_gap_is_a_new_equation(self):
        page = _display_page(_display_line_at(DISPLAY_BOTTOM + LINE_HEIGHT * LINE_MERGE_RATIO + STEP))
        self.assertEqual(len(self._scan(page)["display"]), 2)


class DisplayBandTest(ScanCase):
    """Ortası ayrı satır denkleminin bandına düşen parça o denklemin parçasıdır."""

    def test_run_centred_on_the_band_top_belongs_to_the_display_equation(self):
        self.assertEqual(self._scan(_display_page(_inline_centred_at(DISPLAY_TOP)))["inline"], [])

    def test_run_centred_above_the_band_is_inline(self):
        self.assertEqual(len(self._scan(_display_page(_inline_centred_at(DISPLAY_TOP - STEP)))["inline"]), 1)

    def test_run_centred_on_the_band_bottom_belongs_to_the_display_equation(self):
        self.assertEqual(self._scan(_display_page(_inline_centred_at(DISPLAY_BOTTOM)))["inline"], [])

    def test_run_centred_below_the_band_is_inline(self):
        self.assertEqual(len(self._scan(_display_page(_inline_centred_at(DISPLAY_BOTTOM + STEP)))["inline"]), 1)


class OrderTest(ScanCase):
    def test_font_equations_come_before_geometry_equations(self):
        settings = with_defaults({"math_font_prefix": MATH_FONT, "math_geometry": True})
        display = self._scan(_fraction_above_display(), settings)["display"]
        self.assertEqual([region["y0"] for region in display], [300, 191])

    def test_inline_images_are_numbered_before_display_equations(self):
        result = self._scan(_page())
        self.assertEqual((result["inline"][0]["id"], result["display"][0]["block"]["src"]), ("eq-1", "eq-2.png"))


class NumberingTest(ScanCase):
    """Numarayı yalnız kırpılan denklemler alır; düz metne çevrilen sembol numara tüketmez."""

    def setUp(self):
        super().setUp()
        self.result = self._scan(_images_around_a_symbol())

    def test_inline_images_are_numbered_in_reading_order(self):
        self.assertEqual([item.get("id") for item in self.result["inline"]], ["eq-1", None, "eq-2"])

    def test_display_equations_follow_the_inline_images(self):
        self.assertEqual([region["block"]["src"] for region in self.result["display"]], ["eq-3.png"])


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
        line = (span("area ", (72, 90, 100, 102)), _math("πr", (100, 90, 112, 102)),
                span(" grows", (112, 90, 150, 102)))
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
