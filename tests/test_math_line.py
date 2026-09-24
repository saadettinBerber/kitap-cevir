"""Satırın denklem fontundaki ve düz metindeki parçaları (SpanRun, MathLine)."""
import unittest

from pdf_fakes import span
from extraction.equations.math_line import MathLine, SpanRun

MATH_FONT = "Helvetica-Oblique"


def _is_math(span):
    return span.font == MATH_FONT


def _math(text, x0, x1):
    return span(text, (x0, 90, x1, 102), MATH_FONT, 11)


def _prose(text, x0, x1):
    return span(text, (x0, 90, x1, 102))


def _neighbours(*spans):
    [inline_run] = MathLine(spans, _is_math).inline_runs()
    return inline_run.before, inline_run.after


class SpanRunTest(unittest.TestCase):
    def test_split_groups_consecutive_spans_by_kind(self):
        spans = (_prose("find ", 72, 100), _math("x", 100, 106), _math("2", 106, 110), _prose(" to", 110, 130))
        runs = SpanRun.split(spans, _is_math)
        self.assertEqual([(run.is_math, len(run.spans)) for run in runs], [(False, 1), (True, 2), (False, 1)])


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


if __name__ == "__main__":
    unittest.main()
