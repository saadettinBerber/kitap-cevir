"""Denklemleri düz metinle dizen kitaplarda kesir çizgisinden denklem bulma.
PyMuPDF'in çizgiyi sıfır yükseklikli kutu olarak verdiği test_pdf_boundary'de sabitlidir."""
import tempfile
import unittest

from pdf_fakes import FakePdfPage, span, stroke
from extraction.equations.math_geometry import BAR_GROUP_MAX_SPAN_RATIO, COLUMN_EDGE_TOLERANCE, Rule, TextColumn
from extraction.equations.math_scan import MathScanner
from extraction.pdf.geometry import Box
from extraction.settings import with_defaults

GEOMETRY_ON = {"math_geometry": True}
COLUMN_LEFT = 72
COLUMN_RIGHT = 432
PROSE_TOP = 249
TABLE_RULE_Y = 400
TABLE_RULE_SPLIT = 246

# A = ma / mc: pay, payda ve aralarındaki kesir çizgisi; altında gövde metni.
NUMERATOR = (span("A =", (87, 191, 102, 205)), span("ma", (106, 191, 120, 205)))
DENOMINATOR = (span("mc", (106, 208, 119, 222)),)
PROSE = (span("In the equation, ma represents abstract elements.", (COLUMN_LEFT, PROSE_TOP, 303, 263), size=10.5),)
FRACTION_LINES = (NUMERATOR, DENOMINATOR, PROSE)
FRACTION_BAR = stroke(106, 208, 125, 208)
EQUATION_CAPTION = (span("Equation 3-3. Abstractness", (COLUMN_LEFT, 177, 200, 187)),)


def _table_rule(*stops):
    """Kenarlık tek çizgi ya da (e-kitap dizgisinde olduğu gibi) aynı hizada
    parçalar hâlinde çizilir; stops parçaların uç noktalarıdır."""
    return [stroke(left, TABLE_RULE_Y, right, TABLE_RULE_Y) for left, right in zip(stops, stops[1:])]


def _fraction_page(*shapes):
    return FakePdfPage(lines=list(FRACTION_LINES), shapes=[FRACTION_BAR, *shapes])


def _display(page, settings=GEOMETRY_ON):
    with tempfile.TemporaryDirectory() as images:
        return MathScanner(with_defaults(settings), page, images).scan()["display"]


class GeometryMathTest(unittest.TestCase):
    """Type3 fontu olmayan kitaplarda denklemi kesir çizgisi ele verir."""

    def test_fraction_becomes_one_math_block(self):
        self.assertEqual([region["block"]["type"] for region in _display(_fraction_page())], ["math"])

    def test_region_covers_both_sides_of_the_bar(self):
        [region] = _display(_fraction_page())
        self.assertEqual(region["block"]["text"], "A = ma mc")

    def test_body_text_below_stays_outside(self):
        [region] = _display(_fraction_page())
        self.assertLess(region["y1"], PROSE_TOP)

    def test_caption_above_the_fraction_stays_out_of_the_equation(self):
        """Denklem başlığı denklemin hemen üstündedir ama çevrilecek bir caption'dır."""
        page = FakePdfPage(lines=[EQUATION_CAPTION, *FRACTION_LINES], shapes=[FRACTION_BAR])
        [region] = _display(page)
        self.assertEqual(region["block"]["text"], "A = ma mc")

    def test_full_width_rule_is_not_a_fraction_bar(self):
        self.assertEqual(len(_display(_fraction_page(*_table_rule(COLUMN_LEFT, COLUMN_RIGHT)))), 1)

    def test_segmented_table_rule_is_not_a_fraction_bar(self):
        """Kenarlığın sütun kenarından başlamayan parçası tek başına kesir
        çizgisine benzer; test hizanın tamamına bakılmasını korur."""
        rule = _table_rule(COLUMN_LEFT, TABLE_RULE_SPLIT, COLUMN_RIGHT)
        self.assertEqual(len(_display(_fraction_page(*rule))), 1)

    def test_detection_is_off_by_default(self):
        self.assertEqual(_display(_fraction_page(), settings={}), [])


COLUMN_WIDTH = 300
FRACTION_LEFT = 180
FRACTION_RIGHT = 240
BAR_TOP, BAR_BOTTOM = 150, 151
EDGE = COLUMN_LEFT + COLUMN_EDGE_TOLERANCE
WIDEST_FRACTION = COLUMN_WIDTH * BAR_GROUP_MAX_SPAN_RATIO
SEGMENT_LEFT, SEGMENT_SPLIT, SEGMENT_RIGHT = 150, 200, 300
EDGE_BAR_RIGHT = 120
SHORT_BAR = 20
FULL_LINE = Box(COLUMN_LEFT, 100, COLUMN_LEFT + COLUMN_WIDTH, 110)
SHORT_LINE = Box(COLUMN_LEFT, 120, 360, 130)
STEP = 0.1


def _rule(*spans):
    """spans: aynı hizadaki çizgi parçalarının (sol, sağ) uçları."""
    [rule] = Rule.from_drawings([stroke(left, BAR_TOP, right, BAR_BOTTOM) for left, right in spans])
    return rule


class TextColumnTest(unittest.TestCase):
    def setUp(self):
        self.column = TextColumn([FULL_LINE, SHORT_LINE])

    def test_short_indented_bar_is_a_fraction(self):
        self.assertTrue(self.column.holds_fraction(_rule((FRACTION_LEFT, FRACTION_RIGHT))))

    def test_bar_from_column_edge_is_not_a_fraction(self):
        self.assertFalse(self.column.holds_fraction(_rule((COLUMN_LEFT, EDGE_BAR_RIGHT))))

    def test_bar_starting_at_the_edge_tolerance_is_not_a_fraction(self):
        self.assertFalse(self.column.holds_fraction(_rule((EDGE, EDGE + SHORT_BAR))))

    def test_bar_starting_just_past_the_edge_tolerance_is_a_fraction(self):
        self.assertTrue(self.column.holds_fraction(_rule((EDGE + STEP, EDGE + SHORT_BAR))))

    def test_bar_as_wide_as_the_widest_fraction_is_a_fraction(self):
        self.assertTrue(self.column.holds_fraction(_rule((FRACTION_LEFT, FRACTION_LEFT + WIDEST_FRACTION))))

    def test_bar_just_wider_than_the_widest_fraction_is_not_a_fraction(self):
        right = FRACTION_LEFT + WIDEST_FRACTION + STEP
        self.assertFalse(self.column.holds_fraction(_rule((FRACTION_LEFT, right))))

    def test_segmented_full_width_rule_is_not_a_fraction(self):
        rule = _rule((SEGMENT_LEFT, SEGMENT_SPLIT), (SEGMENT_SPLIT, SEGMENT_RIGHT))
        self.assertFalse(self.column.holds_fraction(rule))


if __name__ == "__main__":
    unittest.main()
