"""Satırın denklem fontundaki ve düz metindeki parçaları (SpanRun, MathLine).
Parçalar metin sırasıyla verilir; kutuları bu kurallarda rol oynamaz, hepsi aynı satır kutusundadır."""
import unittest

from pdf_fakes import span
from extraction.equations.math_line import MathLine, SpanRun

MATH_FONT = "Helvetica-Oblique"
LINE_BOX = (72, 90, 200, 102)


def _is_math(piece):
    return piece.font == MATH_FONT


def _math(text):
    return span(text, LINE_BOX, MATH_FONT)


def _prose(text):
    return span(text, LINE_BOX)


def _neighbours(*spans):
    [inline_run] = MathLine(spans, _is_math).inline_runs()
    return inline_run.before, inline_run.after


class SpanRunTest(unittest.TestCase):
    def test_split_groups_consecutive_spans_by_kind(self):
        runs = SpanRun.split((_prose("find "), _math("x"), _math("2"), _prose(" to")), _is_math)
        self.assertEqual([(run.is_math, len(run.spans)) for run in runs], [(False, 1), (True, 2), (False, 1)])


class MathLineTest(unittest.TestCase):
    """Satır içi denklemin yeri, cümledeki komşu kelimeleriyle bulunur."""

    def test_neighbours_are_the_nearest_words_on_both_sides(self):
        self.assertEqual(_neighbours(_prose("Goal: find "), _math("x"), _prose(" to minimize")), ("find", "to"))

    def test_equation_opening_the_line_has_no_word_before(self):
        self.assertEqual(_neighbours(_math("x"), _prose(" grows fast")), ("", "grows"))

    def test_equation_closing_the_line_has_no_word_after(self):
        self.assertEqual(_neighbours(_prose("it minimizes "), _math("x")), ("minimizes", ""))

    def test_blank_neighbour_gives_no_word(self):
        self.assertEqual(_neighbours(_prose(" "), _math("x")), ("", ""))

    def test_line_all_in_math_font_is_a_display_line(self):
        self.assertTrue(MathLine((_math("E = mc2"),), _is_math).is_display())

    def test_display_line_has_no_inline_runs(self):
        self.assertEqual(MathLine((_math("E = mc2"),), _is_math).inline_runs(), [])

    def test_line_mixing_prose_and_math_is_not_a_display_line(self):
        self.assertFalse(MathLine((_prose("find "), _math("x")), _is_math).is_display())


if __name__ == "__main__":
    unittest.main()
