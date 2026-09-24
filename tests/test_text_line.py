import unittest

from pdf_fakes import span
from extraction.text_layer.script_marks import ScriptMark
from extraction.text_layer.text_line import LineSpan, TextLine

BASELINE = 100.0


def _span(text, x0, is_code, size=10.0, baseline=BASELINE):
    width = len(text) * size * 0.6
    return LineSpan.marked(span(text, (x0, baseline - size, x0 + width, baseline), size=size), is_code)


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


if __name__ == "__main__":
    unittest.main()
