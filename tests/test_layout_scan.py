"""Metin katmanı kuralları sahte sayfayla: PDF açılmaz, satırlar elle dizilir.

Gerçek PyMuPDF satırlarıyla çalışan öğrenme testleri test_code_lines ve
test_prose_scripts'tedir.
"""
import unittest

from pdf_fakes import FakePdfPage, span
from extraction.settings import with_defaults
from extraction.text_layer.code_lines import CodeFont, PageLineReader
from extraction.text_layer.layout_scan import LayoutScanner
from extraction.text_layer.text_line import MONO_CHAR_WIDTH_RATIO

CODE_FONT = "Courier"
CODE_MAX_SIZE = 12.0
SETTINGS = with_defaults({"code_font_prefix": CODE_FONT, "code_max_font_size": CODE_MAX_SIZE})
BODY = "Helvetica"
SIZE = 10.0
LEFT = 72.0


def _piece(text, left, top, font=BODY, size=SIZE):
    """Karakter başına punto × 0.6 genişliğinde parça; taban çizgisi alt kenarıdır."""
    return span(text, (left, top, left + len(text) * size * MONO_CHAR_WIDTH_RATIO, top + size), font, size)


def _code(text, left, top, size=SIZE):
    return _piece(text, left, top, CODE_FONT, size)


def _after(previous, text, font=BODY):
    """Önceki parçanın sağ kenarından, aynı taban çizgisinde başlayan parça."""
    return _piece(text, previous.box.x1, previous.baseline - SIZE, font)


def _raised(previous, text, size, rise):
    """Önceki parçanın sağında, taban çizgisi rise kadar yukarıda parça."""
    return _piece(text, previous.box.x1, previous.baseline - rise - size, BODY, size)


def _lines(*pdf_lines):
    return PageLineReader(CodeFont(SETTINGS)).read(FakePdfPage(lines=list(pdf_lines)))


def _scan(*pdf_lines):
    return LayoutScanner(SETTINGS).scan(FakePdfPage(lines=list(pdf_lines)))


class CodeFontTest(unittest.TestCase):
    def test_code_font_below_the_size_limit_is_code(self):
        [line] = _lines((_code("int x = 1;", LEFT, 100, size=CODE_MAX_SIZE - 0.5),))
        self.assertTrue(line.is_code)

    def test_code_font_at_the_size_limit_is_prose(self):
        [line] = _lines((_code("int x = 1;", LEFT, 100, size=CODE_MAX_SIZE),))
        self.assertFalse(line.is_code)

    def test_other_font_is_prose(self):
        [line] = _lines((_piece("int x = 1;", LEFT, 100),))
        self.assertFalse(line.is_code)


class BaselineSplitTest(unittest.TestCase):
    """PyMuPDF bir satıra farklı taban çizgisindeki parçaları koyabilir."""

    def test_pieces_two_points_apart_share_the_line(self):
        first = _piece("Hello", LEFT, 100)
        [line] = _lines((first, _raised(first, " world", SIZE, rise=2.0)))
        self.assertEqual(line.text, "Hello world")

    def test_pieces_further_apart_become_separate_lines(self):
        first = _piece("Hello", LEFT, 100)
        lines = _lines((first, _raised(first, " world", SIZE, rise=2.5)))
        self.assertEqual(sorted(line.text for line in lines), [" world", "Hello"])


class CodeLineTest(unittest.TestCase):
    def test_code_fragments_on_one_baseline_form_one_line(self):
        head = _code("total = ", LEFT, 100)
        [line] = _lines((head,), (_after(head, "count + 1", CODE_FONT),))
        self.assertEqual((line.is_code, line.text), (True, "total = count + 1"))

    def test_short_code_beside_prose_is_inline_code(self):
        prose = _piece("The value is stored in ", LEFT, 100)
        lines = _lines((prose,), (_after(prose, "count", CODE_FONT),))
        self.assertFalse(any(line.is_code for line in lines))

    def _code_lines_beside_prose(self, code_text):
        code = _code(code_text, LEFT, 100)
        return [line.text for line in _lines((code,), (_after(code, ", or more", BODY),)) if line.is_code]

    def test_leftmost_code_of_twelve_characters_stays_a_code_line(self):
        self.assertEqual(self._code_lines_beside_prose("items.size()"), ["items.size()"])

    def test_leftmost_code_of_eleven_characters_is_inline_code(self):
        self.assertEqual(self._code_lines_beside_prose("items.count"), [])


class InlineCodeTest(unittest.TestCase):
    """Satır içi kod parçaları ODL metninde ters tırnakla işaretlenir."""

    def _tokens(self, *codes):
        pieces = [_piece("Call ", LEFT, 100)]
        for code in codes:
            pieces += [_after(pieces[-1], code, CODE_FONT), _after(pieces[-1], " then ", BODY)]
        return _scan(tuple(pieces))["inline_code"]

    def test_identifier_is_marked(self):
        self.assertEqual(self._tokens("getUser"), ["getUser"])

    def test_plain_lowercase_word_is_not_marked(self):
        self.assertEqual(self._tokens("render"), [])

    def test_single_character_is_not_marked(self):
        self.assertEqual(self._tokens("X"), [])

    def test_two_characters_are_marked(self):
        self.assertEqual(self._tokens("Io"), ["Io"])

    def test_edge_punctuation_is_stripped(self):
        self.assertEqual(self._tokens("getUser()"), ["getUser"])

    def test_repeated_token_is_marked_once(self):
        self.assertEqual(self._tokens("getUser", "setUser", "getUser"), ["getUser", "setUser"])


class CodeBlockTest(unittest.TestCase):
    CHAR = SIZE * MONO_CHAR_WIDTH_RATIO

    def _code_block(self, *tops_and_lefts):
        pdf_lines = [(_code(f"line{i}", left, top),) for i, (top, left) in enumerate(tops_and_lefts)]
        [block] = _scan(*pdf_lines)["code_blocks"]
        return block

    def test_indent_is_counted_in_characters(self):
        block = self._code_block((100, LEFT), (110, LEFT + 4 * self.CHAR))
        self.assertEqual(block["code"], "line0\n    line1")

    def test_block_spans_its_lines(self):
        self.assertEqual({key: value for key, value in self._code_block((100, LEFT), (110, LEFT)).items()
                          if key != "code"}, {"y0": 100, "y1": 110 + SIZE})

    def test_gap_up_to_the_ratio_is_not_a_blank_line(self):
        self.assertEqual(self._code_block((100, LEFT), (100 + SIZE * 1.6, LEFT))["code"], "line0\nline1")

    def test_gap_above_the_ratio_is_a_blank_line(self):
        self.assertEqual(self._code_block((100, LEFT), (100 + SIZE * 1.7, LEFT))["code"], "line0\n\nline1")

    def test_prose_between_listings_splits_them(self):
        pdf_lines = [(_code("a = 1", LEFT, 100),), (_piece("Then the next one:", LEFT, 120),),
                     (_code("b = 2", LEFT, 140),)]
        self.assertEqual([block["code"] for block in _scan(*pdf_lines)["code_blocks"]], ["a = 1", "b = 2"])


class ProseScriptTest(unittest.TestCase):
    """Düz metinde sembole yapışık küçük parça simgedir; dipnot işareti değildir."""

    SCRIPT_RISE = 3.0

    def _script_fixes(self, host_text, script, script_size):
        host = _piece(f"In the equation, {host_text}", LEFT, 100)
        mark = _raised(host, script, script_size, self.SCRIPT_RISE)
        rest = _piece(" represents the ratio.", mark.box.x1, host.box.y0)
        return _scan((host, mark, rest))["script_fixes"]

    def test_superscript_on_a_symbol_becomes_unicode(self):
        self.assertEqual(self._script_fixes("m", "a", SIZE * 0.8), {"ma": "mᵃ"})

    def test_mark_smaller_than_the_script_ratio_is_a_footnote(self):
        self.assertEqual(self._script_fixes("m", "a", SIZE * 0.65), {})

    def test_mark_as_large_as_the_script_ratio_is_not_a_script(self):
        self.assertEqual(self._script_fixes("m", "a", SIZE * 0.85), {})

    def test_mark_after_a_long_word_is_a_footnote(self):
        self.assertEqual(self._script_fixes("ratio", "a", SIZE * 0.8), {})


class LayoutScannerTest(unittest.TestCase):
    def test_empty_page_has_nothing_to_repair(self):
        self.assertEqual(_scan(), {"page_height": 800.0, "code_blocks": [], "inline_code": [], "hyphen_fixes": {},
                                   "script_fixes": {}, "code_image_links": []})


if __name__ == "__main__":
    unittest.main()
