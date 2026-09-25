"""Denklemleri düz metinle dizen kitaplarda kesir çizgisinden denklem bulma.
PyMuPDF'in çizgiyi sıfır yükseklikli kutu olarak verdiği test_pdf_boundary'de sabitlidir."""
import tempfile
import unittest

from pdf_fakes import FakePdfPage, span, stroke
from extraction.equations.math_geometry import (
    BAR_GROUP_MAX_SPAN_RATIO, BAR_GROUP_Y_TOLERANCE, BAR_MAX_HEIGHT, BAR_MIN_WIDTH, COLUMN_EDGE_TOLERANCE,
    EQUATION_LINE_GAP, MAX_GROWTH_PASSES, FractionEquationFinder, Rule, TextColumn)
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


BAR_Y = 207
LINE_HEIGHT = 12
BODY = Box(COLUMN_LEFT, 500, COLUMN_RIGHT, 512)
SECOND_BAR_LEFT = 260


def _regions(*drawings):
    """Gövde satırı sütunu belirler; kesir çizgisinin çevresinde metin yok."""
    return FractionEquationFinder([BODY]).regions(list(drawings))


def _bar(width, height):
    return stroke(FRACTION_LEFT, BAR_Y, FRACTION_LEFT + width, BAR_Y + height)


def _line_below(top):
    return Box(FRACTION_LEFT, top, FRACTION_RIGHT, top + LINE_HEIGHT)


def _grown_bottom(*lines):
    """Kesir çizgisi ile altındaki satırlardan büyüyen tek bölgenin alt kenarı."""
    [region] = FractionEquationFinder([BODY, *lines]).regions([_bar(FRACTION_RIGHT - FRACTION_LEFT, 0)])
    return region.y1


def _chain_below(count):
    """Çizginin altında, her biri bir öncekinden tam en büyük boşluk kadar uzak satırlar."""
    pitch = LINE_HEIGHT + EQUATION_LINE_GAP
    return [_line_below(BAR_Y + EQUATION_LINE_GAP + index * pitch) for index in range(count)]


class BarShapeTest(unittest.TestCase):
    """Kesir çizgisi ince ve kısa bir yatay çizgidir; kalını dolgu, çok kısası nokta ya da imdir."""

    def test_bar_as_thick_as_the_limit_is_a_bar(self):
        self.assertEqual(len(_regions(_bar(SHORT_BAR, BAR_MAX_HEIGHT))), 1)

    def test_bar_thicker_than_the_limit_is_a_fill(self):
        self.assertEqual(_regions(_bar(SHORT_BAR, BAR_MAX_HEIGHT + STEP)), [])

    def test_bar_as_short_as_the_limit_is_a_bar(self):
        self.assertEqual(len(_regions(_bar(BAR_MIN_WIDTH, 0))), 1)

    def test_bar_shorter_than_the_limit_is_not_a_bar(self):
        self.assertEqual(_regions(_bar(BAR_MIN_WIDTH - STEP, 0)), [])

    def test_page_without_text_lines_has_no_equations(self):
        self.assertEqual(FractionEquationFinder([]).regions([_bar(SHORT_BAR, 0)]), [])


def _edge_segment_and(segment_y):
    """Sütun kenarından başlayan tablo kenarlığı parçası ve ondan sonra çizilen kısa bir parça."""
    return (stroke(COLUMN_LEFT, BAR_Y, SEGMENT_RIGHT, BAR_Y),
            stroke(SECOND_BAR_LEFT, segment_y, SECOND_BAR_LEFT + SHORT_BAR, segment_y))


class RuleLevelTest(unittest.TestCase):
    def test_segment_within_the_tolerance_belongs_to_the_edge_rule(self):
        self.assertEqual(_regions(*_edge_segment_and(BAR_Y + BAR_GROUP_Y_TOLERANCE)), [])

    def test_segment_past_the_tolerance_is_a_bar_of_its_own(self):
        self.assertEqual(len(_regions(*_edge_segment_and(BAR_Y + BAR_GROUP_Y_TOLERANCE + STEP))), 1)

    def test_level_is_measured_from_the_first_segment_of_the_rule(self):
        """Her parça bir öncekine tolerans kadar yakın olsa da ilk parçadan uzaklaşan parça yeni kuraldır."""
        half_step = BAR_GROUP_Y_TOLERANCE * 0.8
        edge, segment = _edge_segment_and(BAR_Y + 2 * half_step)
        middle = stroke(COLUMN_LEFT, BAR_Y + half_step, SEGMENT_RIGHT, BAR_Y + half_step)
        self.assertEqual(len(_regions(edge, middle, segment)), 1)

    def test_segments_are_grouped_in_vertical_order_not_drawing_order(self):
        edge, segment = _edge_segment_and(BAR_Y)
        lower_bar = stroke(FRACTION_LEFT, TABLE_RULE_Y, FRACTION_RIGHT, TABLE_RULE_Y)
        self.assertEqual(len(_regions(edge, lower_bar, segment)), 1)


class GrowthTest(unittest.TestCase):
    """Bölge, kesir çizgisinden başlayıp en büyük boşluk kadar yakın satırları toplayarak büyür."""

    def test_line_at_the_gap_joins_the_equation(self):
        line = _line_below(BAR_Y + EQUATION_LINE_GAP)
        self.assertEqual(_grown_bottom(line), line.y1)

    def test_line_past_the_gap_stays_out(self):
        self.assertEqual(_grown_bottom(_line_below(BAR_Y + EQUATION_LINE_GAP + STEP)), BAR_Y)

    def test_growth_stops_after_the_last_pass(self):
        """Her geçiş bir komşu satır ekler; son geçişin satırı girer, sonrakiler dışarıda kalır."""
        chain = _chain_below(MAX_GROWTH_PASSES + 1)
        self.assertEqual(_grown_bottom(*chain), chain[MAX_GROWTH_PASSES - 1].y1)

    def test_every_bar_of_a_fraction_rule_is_grown(self):
        second_bar = stroke(SECOND_BAR_LEFT, BAR_Y, SECOND_BAR_LEFT + SHORT_BAR, BAR_Y)
        self.assertEqual(len(_regions(_bar(SHORT_BAR, 0), second_bar)), 2)

    def test_two_bars_of_one_equation_make_one_region(self):
        second_bar = stroke(SECOND_BAR_LEFT, BAR_Y, SECOND_BAR_LEFT + SHORT_BAR, BAR_Y)
        shared_line = Box(FRACTION_LEFT, BAR_Y + EQUATION_LINE_GAP, SECOND_BAR_LEFT + SHORT_BAR, BAR_Y + LINE_HEIGHT)
        regions = FractionEquationFinder([BODY, shared_line]).regions([_bar(SHORT_BAR, 0), second_bar])
        self.assertEqual(len(regions), 1)


if __name__ == "__main__":
    unittest.main()
