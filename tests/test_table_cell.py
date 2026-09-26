"""Tablo hücresi: satırları, üst simgeleri ve satır sonları. Satır sonlarını yalnız liste
niteliğindeki çok satırlı hücreler korur; sütunu dolduran satırlar sarılmış düz metindir."""
import dataclasses
import unittest

from pdf_fakes import sized, span
from extraction.pdf.geometry import Box
from extraction.tables.table_cell import SUPERSCRIPT_RATIO, WRAP_FILL_RATIO, CellText, TableCell

LEFT, RIGHT = 70, 170
COLUMN = (LEFT, RIGHT)
MAIN_SIZE = 10.0
TEXT_LEFT = 72
SHORT_RIGHT = 100
FULL_RIGHT = 160
FIRST_LINE, SECOND_LINE, THIRD_LINE = 100, 112, 124
STEP = 0.1


def _span(text, line_y):
    return sized(MAIN_SIZE, span(text, (TEXT_LEFT, line_y, SHORT_RIGHT, line_y + MAIN_SIZE)))


def _reaching(right, piece):
    """Aynı parça, sağ kenarı right'ta."""
    return dataclasses.replace(piece, box=Box(piece.box.x0, piece.box.y0, right, piece.box.y1))


def _sized(size, piece):
    return dataclasses.replace(piece, size=size)


def _right_at(fill):
    """Sütunun `fill` oranını dolduran satırın sağ kenarı."""
    return LEFT + (RIGHT - LEFT) * fill


def _cell(*spans):
    return TableCell(CellText(list(spans), MAIN_SIZE), COLUMN)


class LinesTest(unittest.TestCase):
    def test_words_of_a_line_are_joined_with_spaces(self):
        self.assertEqual(_cell(_span("one", FIRST_LINE), _span("two", FIRST_LINE)).unit(), {"en": "one two"})

    def test_lines_are_read_from_top_to_bottom(self):
        self.assertEqual(_cell(_span("second", SECOND_LINE), _span("first", FIRST_LINE)).unit(), {"en": "first second"})

    def test_text_is_escaped_when_the_cell_is_html(self):
        self.assertEqual(_cell(_span("a<b", FIRST_LINE), _span("c", SECOND_LINE)).listing_unit(),
                         {"en": "a&lt;b<br>c", "html": True})


class SuperscriptTest(unittest.TestCase):
    def test_span_below_the_ratio_is_a_superscript(self):
        mark = _sized(MAIN_SIZE * SUPERSCRIPT_RATIO - STEP, _span("a", FIRST_LINE))
        self.assertEqual(_cell(_span("Latency", FIRST_LINE), mark).unit(), {"en": "Latency<sup>a</sup>", "html": True})

    def test_span_at_the_ratio_is_text(self):
        mark = _sized(MAIN_SIZE * SUPERSCRIPT_RATIO, _span("a", FIRST_LINE))
        self.assertEqual(_cell(_span("Latency", FIRST_LINE), mark).unit(), {"en": "Latency a"})

    def test_lines_stay_joined_with_spaces_before_the_superscripts(self):
        mark = _sized(MAIN_SIZE / 2, _span("a", FIRST_LINE))
        self.assertEqual(_cell(_span("one", FIRST_LINE), _span("two", SECOND_LINE), mark).unit(),
                         {"en": "one two<sup>a</sup>", "html": True})


class MultilineTest(unittest.TestCase):
    def test_superscript_on_its_own_line_makes_the_cell_multiline(self):
        mark = _sized(MAIN_SIZE / 2, _span("a", SECOND_LINE))
        self.assertTrue(_cell(_span("one", FIRST_LINE), mark).is_multiline())


class WrappedProseTest(unittest.TestCase):
    def test_single_line_cell_stays_plain_text_when_the_row_keeps_breaks(self):
        self.assertEqual(_cell(_span("one", FIRST_LINE)).listing_unit(), {"en": "one"})

    def test_line_filling_the_column_to_the_ratio_is_wrapped_prose(self):
        pieces = (_reaching(_right_at(WRAP_FILL_RATIO), _span("one", FIRST_LINE)), _span("two", SECOND_LINE))
        self.assertEqual(_cell(*pieces).listing_unit(), {"en": "one two"})

    def test_line_just_short_of_the_ratio_keeps_its_break(self):
        pieces = (_reaching(_right_at(WRAP_FILL_RATIO) - STEP, _span("one", FIRST_LINE)), _span("two", SECOND_LINE))
        self.assertEqual(_cell(*pieces).listing_unit(), {"en": "one<br>two", "html": True})

    def test_line_right_edge_is_its_widest_span(self):
        pieces = (_reaching(FULL_RIGHT, _span("long", FIRST_LINE)), _span("x", FIRST_LINE), _span("two", SECOND_LINE))
        self.assertEqual(_cell(*pieces).listing_unit(), {"en": "long x two"})

    def test_last_line_does_not_count_towards_the_fill(self):
        pieces = (_reaching(FULL_RIGHT, _span("full", FIRST_LINE)), _span("short", SECOND_LINE),
                  _span("end", THIRD_LINE))
        self.assertEqual(_cell(*pieces).listing_unit(), {"en": "full short end"})


if __name__ == "__main__":
    unittest.main()
