"""Denklemleri düz metinle dizen kitaplarda kesir çizgisinden denklem bulma.
PyMuPDF'in çizgiyi sıfır yükseklikli kutu olarak verdiği test_pdf_boundary'de sabitlidir."""
import tempfile
import unittest

from pdf_fakes import FakePdfPage, span, stroke
from extraction.equations.math_geometry import BAR_GROUP_MAX_SPAN_RATIO, COLUMN_EDGE_TOLERANCE, Rule, TextColumn
from extraction.equations.math_scan import MathScanner
from extraction.pdf.geometry import Box
from extraction.settings import with_defaults

SETTINGS = {"math_geometry": True}
COLUMN_LEFT = 72
COLUMN_RIGHT = 432
PROSE_TOP = 249
TABLE_RULE_Y = 400
TABLE_RULE_SPLIT = 246

# A = ma / mc: pay, payda ve aralarındaki kesir çizgisi; altında gövde metni.
NUMERATOR = (span("A =", (87, 191, 102, 205)), span("ma", (106, 191, 120, 205)))
DENOMINATOR = (span("mc", (106, 208, 119, 222)),)
PROSE = (span("In the equation, ma represents abstract elements.", (COLUMN_LEFT, PROSE_TOP, 303, 263), size=10.5),)
FRACTION_BAR = stroke(106, 208, 125, 208)


def _table_rule(*stops):
    """Kenarlık tek çizgi ya da (e-kitap dizgisinde olduğu gibi) aynı hizada
    parçalar hâlinde çizilir; stops parçaların uç noktalarıdır."""
    return [stroke(left, TABLE_RULE_Y, right, TABLE_RULE_Y) for left, right in zip(stops, stops[1:])]


def _scan(*shapes, settings=SETTINGS):
    page = FakePdfPage(lines=[NUMERATOR, DENOMINATOR, PROSE], shapes=[FRACTION_BAR, *shapes])
    with tempfile.TemporaryDirectory() as images:
        return MathScanner(with_defaults(settings), page, images).scan()


class GeometryMathTest(unittest.TestCase):
    """Type3 fontu olmayan kitaplarda denklemi kesir çizgisi ele verir."""

    def test_fraction_becomes_one_math_block(self):
        display = _scan()["display"]
        self.assertEqual(len(display), 1)
        self.assertEqual(display[0]["block"]["type"], "math")

    def test_region_covers_both_sides_of_the_bar(self):
        text = _scan()["display"][0]["block"]["text"]
        for part in ("A =", "ma", "mc"):
            self.assertIn(part, text)

    def test_body_text_below_stays_outside(self):
        [region] = _scan()["display"]
        self.assertLess(region["y1"], PROSE_TOP)
        self.assertNotIn("represents", region["block"]["text"])

    def test_full_width_rule_is_not_a_fraction_bar(self):
        self.assertEqual(len(_scan(*_table_rule(COLUMN_LEFT, COLUMN_RIGHT))["display"]), 1)

    def test_segmented_table_rule_is_not_a_fraction_bar(self):
        """Kenarlığın sütun kenarından başlamayan parçası tek başına kesir
        çizgisine benzer; test hizanın tamamına bakılmasını korur."""
        self.assertEqual(len(_scan(*_table_rule(COLUMN_LEFT, TABLE_RULE_SPLIT, COLUMN_RIGHT))["display"]), 1)

    def test_detection_is_off_by_default(self):
        self.assertEqual(_scan(settings={})["display"], [])


COLUMN_WIDTH = 300
FRACTION_LEFT = 180
EDGE = COLUMN_LEFT + COLUMN_EDGE_TOLERANCE
WIDEST_FRACTION = COLUMN_WIDTH * BAR_GROUP_MAX_SPAN_RATIO
STEP = 0.1


class TextColumnTest(unittest.TestCase):
    def setUp(self):
        self.column = TextColumn([Box(COLUMN_LEFT, 100, COLUMN_LEFT + COLUMN_WIDTH, 110),
                                  Box(COLUMN_LEFT, 120, 360, 130)])

    def _rule(self, *bars):
        [rule] = Rule.from_drawings([stroke(*bar) for bar in bars])
        return rule

    def test_short_indented_bar_is_a_fraction(self):
        self.assertTrue(self.column.holds_fraction(self._rule((FRACTION_LEFT, 150, 240, 151))))

    def test_bar_from_column_edge_is_not_a_fraction(self):
        self.assertFalse(self.column.holds_fraction(self._rule((COLUMN_LEFT, 150, 120, 151))))

    def test_bar_starting_at_the_edge_tolerance_is_not_a_fraction(self):
        self.assertFalse(self.column.holds_fraction(self._rule((EDGE, 150, EDGE + 20, 151))))

    def test_bar_starting_just_past_the_edge_tolerance_is_a_fraction(self):
        self.assertTrue(self.column.holds_fraction(self._rule((EDGE + STEP, 150, EDGE + 20, 151))))

    def test_bar_as_wide_as_the_widest_fraction_is_a_fraction(self):
        self.assertTrue(self.column.holds_fraction(self._rule((FRACTION_LEFT, 150, FRACTION_LEFT + WIDEST_FRACTION, 151))))

    def test_bar_just_wider_than_the_widest_fraction_is_not_a_fraction(self):
        right = FRACTION_LEFT + WIDEST_FRACTION + STEP
        self.assertFalse(self.column.holds_fraction(self._rule((FRACTION_LEFT, 150, right, 151))))

    def test_segmented_full_width_rule_is_not_a_fraction(self):
        rule = self._rule((150, 150, 200, 151), (200, 150, 300, 151))
        self.assertFalse(self.column.holds_fraction(rule))


if __name__ == "__main__":
    unittest.main()
