"""Metin satırı (TextLine) ve simge (ScriptMark) kuralları. Parçalar aynı taban çizgisinde,
10 puntoda ve karakter başına 6 punto genişliğindedir."""
import unittest

from pdf_fakes import sized, span
from extraction.text_layer.script_marks import ScriptMark
from extraction.text_layer.text_line import MONO_CHAR_WIDTH_RATIO, LineSpan, TextLine

BASELINE = 100.0
SIZE = 10.0
CHAR_WIDTH = SIZE * MONO_CHAR_WIDTH_RATIO
LEFT = 10.0


def _span(text, left):
    return sized(SIZE, span(text, (left, BASELINE - SIZE, left + len(text) * CHAR_WIDTH, BASELINE)))


def _code(*pieces):
    """pieces: (metin, sol kenar); kod fontuyla dizilmiş parçalar."""
    return [LineSpan.marked(_span(*piece), True) for piece in pieces]


def _prose(*pieces):
    """pieces: (metin, sol kenar); düz metin parçaları."""
    return [LineSpan.marked(_span(*piece), False) for piece in pieces]


def _end(text):
    """Soldan başlayan metnin hemen sağındaki konum."""
    return LEFT + len(text) * CHAR_WIDTH


class TextLineTest(unittest.TestCase):
    def test_line_of_code_spans_is_code(self):
        self.assertTrue(TextLine.of_spans(_code(("int x", LEFT), (" = 1;", _end("int x")))).is_code)

    def test_box_covers_the_spans(self):
        line = TextLine.of_spans(_code(("int x", LEFT), (" = 1;", _end("int x"))))
        self.assertEqual((line.box.x0, line.box.y0, line.box.x1), (LEFT, BASELINE - SIZE, _end("int x = 1;")))


class ScriptMarkTest(unittest.TestCase):
    def test_known_characters_become_unicode(self):
        self.assertEqual(ScriptMark(TextLine.of_spans(_prose(("23", LEFT))), "^").as_unicode(), "²³")

    def test_unknown_characters_keep_marker_notation(self):
        self.assertEqual(ScriptMark(TextLine.of_spans(_prose(("K", LEFT))), "_").as_unicode(), "_K")


if __name__ == "__main__":
    unittest.main()
