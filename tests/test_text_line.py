import unittest

import fitz

import _paths  # noqa: F401
from math_geometry import Rule, TextColumn
from math_scan import SpanRun
from script_marks import ScriptMark
from text_line import TextLine

BASELINE = 100.0


def _span(text, x0, is_code, size=10.0, baseline=BASELINE):
    width = len(text) * size * 0.6
    return {"text": text, "is_code": is_code, "size": size, "origin": (x0, baseline),
            "bbox": (x0, baseline - size, x0 + width, baseline)}


class TextLineTest(unittest.TestCase):
    def test_bbox_and_code_flag_come_from_spans(self):
        line = TextLine.of_spans([_span("int x", 10, True), _span(" = 1;", 40, True)])
        self.assertTrue(line.is_code)
        self.assertEqual((line.left, line.top, line.right), (10, BASELINE - 10, 70))

    def test_long_leading_code_is_split_from_prose(self):
        line = TextLine.of_spans([_span("count(items) + 1", 10, True), _span(", or more", 110, False)])
        code, prose = line.split_leading_code()
        self.assertEqual((code.is_code, code.raw_text), (True, "count(items) + 1"))
        self.assertEqual((prose.is_code, prose.raw_text), (False, ", or more"))

    def test_short_leading_code_stays_inline(self):
        line = TextLine.of_spans([_span("W", 10, True), _span(" is the key", 16, False)])
        self.assertEqual(line.split_leading_code(), [line])

    def test_absorb_merges_fragments_on_one_baseline(self):
        line = TextLine.of_spans([_span("a = ", 10, True)])
        line.absorb(TextLine.of_spans([_span("b", 60, True)]))
        self.assertEqual((line.raw_text, line.right), ("a = b", 66))


class ScriptMarkTest(unittest.TestCase):
    def test_known_characters_become_unicode(self):
        part = TextLine.of_spans([_span("23", 10, False, size=7)])
        self.assertEqual(ScriptMark(part, "^").as_unicode(), "²³")

    def test_unknown_characters_keep_marker_notation(self):
        part = TextLine.of_spans([_span("K", 10, False, size=7)])
        self.assertEqual(ScriptMark(part, "_").as_unicode(), "_K")


class SpanRunTest(unittest.TestCase):
    def test_split_groups_consecutive_spans_by_kind(self):
        spans = [{"font": name} for name in ("Body", "Type3a", "Type3b", "Body")]
        runs = SpanRun.split(spans, lambda span: span["font"].startswith("Type3"))
        self.assertEqual([(run.is_math, len(run.spans)) for run in runs], [(False, 1), (True, 2), (False, 1)])


class TextColumnTest(unittest.TestCase):
    def setUp(self):
        self.column = TextColumn([fitz.Rect(72, 100, 372, 110), fitz.Rect(72, 120, 360, 130)])

    def _rule(self, *bars):
        rule = Rule(fitz.Rect(*bars[0]))
        rule.bars += [fitz.Rect(*bar) for bar in bars[1:]]
        return rule

    def test_short_indented_bar_is_a_fraction(self):
        self.assertTrue(self.column.holds_fraction(self._rule((180, 150, 240, 151))))

    def test_bar_from_column_edge_is_not_a_fraction(self):
        self.assertFalse(self.column.holds_fraction(self._rule((72, 150, 120, 151))))

    def test_segmented_full_width_rule_is_not_a_fraction(self):
        rule = self._rule((150, 150, 200, 151), (200, 150, 300, 151))
        self.assertFalse(self.column.holds_fraction(rule))


if __name__ == "__main__":
    unittest.main()
