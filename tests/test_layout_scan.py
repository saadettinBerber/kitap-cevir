"""Metin katmanı kuralları sahte sayfayla: PDF açılmaz, satırlar elle dizilir.

Sahtelerin satır dizilişinin dayandığı PyMuPDF davranışı test_pdf_boundary'deki
öğrenme testlerindedir.
"""
import unittest

from pdf_fakes import PAGE_HEIGHT, FakePdfPage, span
from extraction.settings import with_defaults
from extraction.text_layer.code_lines import CodeFont, PageLineReader
from extraction.text_layer.script_marks import (PROSE_SCRIPT_MAX_GAP, PROSE_SCRIPT_MIN_SIZE_RATIO, SCRIPT_RUN_MAX_GAP,
                                                SCRIPT_SIZE_RATIO)
from extraction.text_layer.layout_scan import BLANK_LINE_GAP_RATIO, LayoutScanner
from extraction.text_layer.text_line import MONO_CHAR_WIDTH_RATIO, SAME_BASELINE_TOLERANCE

CODE_FONT = "Courier"
CODE_MAX_SIZE = 12.0
SETTINGS = with_defaults({"code_font_prefix": CODE_FONT, "code_max_font_size": CODE_MAX_SIZE})
BODY_FONT = "Helvetica"
SIZE = 10.0
LEFT = 72.0
TOP = 100.0
STEP = 0.1
CHAR_WIDTH = SIZE * MONO_CHAR_WIDTH_RATIO
SCRIPT_SIZE = SIZE * 0.8      # dipnot işaretinden büyük, simge oranının altında
SCRIPT_RISE = 3.0


class Pen:
    """Parça yazar; font ve punto kalemindir. Karakter başına punto × 0.6 genişlik, taban çizgisi alt kenar."""

    def __init__(self, font=BODY_FONT, size=SIZE):
        self._font, self._size = font, size

    def at(self, text, corner):
        """corner: parçanın (sol, üst) köşesi."""
        left, top = corner
        right = left + len(text) * self._size * MONO_CHAR_WIDTH_RATIO
        return span(text, (left, top, right, top + self._size), self._font, self._size)

    def on_baseline(self, text, point):
        """point: parçanın (sol, taban çizgisi) noktası."""
        left, baseline = point
        return self.at(text, (left, baseline - self._size))

    def after(self, previous, text):
        """Önceki parçanın sağ kenarından, aynı taban çizgisinde başlayan parça."""
        return self.on_baseline(text, _end_of(previous))


def _end_of(previous, rise=0.0):
    """Önceki parçanın sağ kenarı ve rise kadar yukarı kaldırılmış taban çizgisi."""
    return previous.box.x1, previous.baseline - rise


BODY = Pen()
CODE = Pen(CODE_FONT)
SCRIPT = Pen(BODY_FONT, SCRIPT_SIZE)


def _lines(*pdf_lines):
    return PageLineReader(CodeFont(SETTINGS)).read(FakePdfPage(lines=list(pdf_lines)))


def _scan(*pdf_lines):
    return LayoutScanner(SETTINGS).scan(FakePdfPage(lines=list(pdf_lines)))


class CodeFontTest(unittest.TestCase):
    STATEMENT = "int x = 1;"

    def test_code_font_below_the_size_limit_is_code(self):
        [line] = _lines((Pen(CODE_FONT, CODE_MAX_SIZE - STEP).at(self.STATEMENT, (LEFT, TOP)),))
        self.assertTrue(line.is_code)

    def test_code_font_at_the_size_limit_is_prose(self):
        [line] = _lines((Pen(CODE_FONT, CODE_MAX_SIZE).at(self.STATEMENT, (LEFT, TOP)),))
        self.assertFalse(line.is_code)

    def test_other_font_is_prose(self):
        [line] = _lines((BODY.at(self.STATEMENT, (LEFT, TOP)),))
        self.assertFalse(line.is_code)


class BaselineSplitTest(unittest.TestCase):
    """PyMuPDF bir satıra farklı taban çizgisindeki parçaları koyabilir."""

    def test_pieces_at_the_baseline_tolerance_share_the_line(self):
        first = BODY.at("Hello", (LEFT, TOP))
        [line] = _lines((first, BODY.on_baseline(" world", _end_of(first, SAME_BASELINE_TOLERANCE))))
        self.assertEqual(line.text, "Hello world")

    def test_pieces_further_apart_become_separate_lines(self):
        first = BODY.at("Hello", (LEFT, TOP))
        lines = _lines((first, BODY.on_baseline(" world", _end_of(first, SAME_BASELINE_TOLERANCE + STEP))))
        self.assertEqual(sorted(line.text for line in lines), [" world", "Hello"])


def _code_lines_beside_prose(code_text):
    code = CODE.at(code_text, (LEFT, TOP))
    return [line.text for line in _lines((code,), (BODY.after(code, ", or more"),)) if line.is_code]


class CodeLineTest(unittest.TestCase):
    def test_code_fragments_on_one_baseline_form_one_line(self):
        head = CODE.at("total = ", (LEFT, TOP))
        [line] = _lines((head,), (CODE.after(head, "count + 1"),))
        self.assertEqual((line.is_code, line.text), (True, "total = count + 1"))

    def test_short_code_beside_prose_is_inline_code(self):
        prose = BODY.at("The value is stored in ", (LEFT, TOP))
        lines = _lines((prose,), (CODE.after(prose, "count"),))
        self.assertFalse(any(line.is_code for line in lines))

    def test_leftmost_code_of_twelve_characters_stays_a_code_line(self):
        self.assertEqual(_code_lines_beside_prose("items.size()"), ["items.size()"])

    def test_leftmost_code_of_eleven_characters_is_inline_code(self):
        self.assertEqual(_code_lines_beside_prose("items.count"), [])


class CodeScriptTest(unittest.TestCase):
    """PyMuPDF üst simgeyi ev sahibiyle aynı satırda, kendi taban çizgisiyle verir."""

    EXPONENT = Pen(CODE_FONT, 7.0)
    RISE = 5.0
    FAR_LEFT = 200
    UNDER_A_CHARACTER = CHAR_WIDTH * 0.75

    def _exponent_line(self):
        """'(3 x 10' + yukarıda küçük '23' + ') ='."""
        head = CODE.at("(3 x 10", (LEFT, TOP))
        script = self.EXPONENT.on_baseline("23", _end_of(head, self.RISE))
        return head, script, CODE.at(") =", (script.box.x1, TOP))

    def test_superscript_joins_its_code_line_with_a_caret(self):
        [line] = _lines(self._exponent_line())
        self.assertEqual((line.is_code, line.text), (True, "(3 x 10^23) ="))

    def test_piece_closer_than_a_character_after_the_superscript_is_not_spaced(self):
        head, script, _ = self._exponent_line()
        tail = CODE.at(") =", (script.box.x1 + self.UNDER_A_CHARACTER, TOP))
        [line] = _lines((head, script, tail))
        self.assertEqual(line.text, "(3 x 10^23) =")

    def test_superscript_in_code_gives_no_prose_word_fix(self):
        self.assertEqual(_scan(self._exponent_line())["script_fixes"], {})

    def test_lowered_small_piece_is_a_subscript(self):
        head = CODE.at("x = K", (LEFT, TOP))
        [line] = _lines((head, self.EXPONENT.on_baseline("i", _end_of(head, -self.RISE))))
        self.assertEqual(line.text, "x = K_i")

    def test_small_piece_raised_more_than_a_line_is_no_superscript(self):
        head = CODE.at("(3 x 10", (LEFT, TOP))
        far = self.EXPONENT.on_baseline("23", _end_of(head, SIZE + STEP))
        self.assertEqual([line.text for line in _lines((head, far))], ["23", "(3 x 10"])

    def test_far_fragment_joins_the_code_line_after_its_superscript(self):
        [line] = _lines(self._exponent_line(), (CODE.at("236 days", (self.FAR_LEFT, TOP)),))
        self.assertRegex(line.text, r"^\(3 x 10\^23\) =.*236 days$")


def _tokens(*codes):
    """'Call ' + her kod parçası ve ardından ' then '; ODL metninde işaretlenecek parçalar."""
    pieces = [BODY.at("Call ", (LEFT, TOP))]
    for code in codes:
        pieces += [CODE.after(pieces[-1], code), BODY.after(pieces[-1], " then ")]
    return _scan(tuple(pieces))["inline_code"]


class InlineCodeTest(unittest.TestCase):
    """Satır içi kod parçaları ODL metninde ters tırnakla işaretlenir."""

    def test_identifier_is_marked(self):
        self.assertEqual(_tokens("getUser"), ["getUser"])

    def test_plain_lowercase_word_is_not_marked(self):
        self.assertEqual(_tokens("render"), [])

    def test_single_character_is_not_marked(self):
        self.assertEqual(_tokens("X"), [])

    def test_two_characters_are_marked(self):
        self.assertEqual(_tokens("Io"), ["Io"])

    def test_edge_punctuation_is_stripped(self):
        self.assertEqual(_tokens("getUser()"), ["getUser"])

    def test_repeated_token_is_marked_once(self):
        self.assertEqual(_tokens("getUser", "setUser", "getUser"), ["getUser", "setUser"])

    def test_code_line_gives_no_inline_code(self):
        self.assertEqual(_scan((CODE.at("int total = 0;", (LEFT, TOP)),))["inline_code"], [])

    def test_prose_line_with_a_code_formula_is_marked_whole(self):
        host = BODY.at("Energy ", (LEFT, TOP))
        code = CODE.after(host, "10")
        exponent = Pen(CODE_FONT, SCRIPT_SIZE).on_baseline("23", _end_of(code, SCRIPT_RISE))
        self.assertEqual(_scan((host, code, exponent))["inline_code"], ["Energy 10^23"])


def _code_block(*corners):
    """Her köşede bir kod satırı ('line0', 'line1', ...); tek kod bloğu beklenir."""
    [block] = _scan(*[(CODE.at(f"line{index}", corner),) for index, corner in enumerate(corners)])["code_blocks"]
    return block


class CodeBlockTest(unittest.TestCase):
    NEXT_LINE = TOP + SIZE
    BLANK_LINE_GAP = SIZE * BLANK_LINE_GAP_RATIO
    INDENT = 4
    LINE_PITCH = 2 * SIZE

    def test_indent_is_counted_in_characters(self):
        block = _code_block((LEFT, TOP), (LEFT + self.INDENT * CHAR_WIDTH, self.NEXT_LINE))
        self.assertEqual(block["code"], "line0\n    line1")

    def test_block_spans_its_lines(self):
        block = _code_block((LEFT, TOP), (LEFT, self.NEXT_LINE))
        self.assertEqual((block["y0"], block["y1"]), (TOP, self.NEXT_LINE + SIZE))

    def test_gap_up_to_the_ratio_is_not_a_blank_line(self):
        self.assertEqual(_code_block((LEFT, TOP), (LEFT, TOP + self.BLANK_LINE_GAP))["code"], "line0\nline1")

    def test_gap_above_the_ratio_is_a_blank_line(self):
        block = _code_block((LEFT, TOP), (LEFT, TOP + self.BLANK_LINE_GAP + SIZE * STEP))
        self.assertEqual(block["code"], "line0\n\nline1")

    def test_prose_between_listings_splits_them(self):
        pdf_lines = [(CODE.at("a = 1", (LEFT, TOP)),), (BODY.at("Then the next one:", (LEFT, TOP + self.LINE_PITCH)),),
                     (CODE.at("b = 2", (LEFT, TOP + 2 * self.LINE_PITCH)),)]
        self.assertEqual([block["code"] for block in _scan(*pdf_lines)["code_blocks"]], ["a = 1", "b = 2"])


def _host(symbol):
    return BODY.at(f"In the equation, {symbol}", (LEFT, TOP))


def _fixes_around(host, marks):
    """Ev sahibi + simge parçaları + ' represents the ratio.' satırının gövde metni düzeltmeleri."""
    rest = BODY.at(" represents the ratio.", (marks[-1].box.x1, host.box.y0))
    return _scan((host, *marks, rest))["script_fixes"]


def _script_fixes(symbol, script):
    host = _host(symbol)
    return _fixes_around(host, [SCRIPT.on_baseline(script, _end_of(host, SCRIPT_RISE))])


def _fixes_with_mark_size(size):
    host = _host("m")
    return _fixes_around(host, [Pen(BODY_FONT, size).on_baseline("a", _end_of(host, SCRIPT_RISE))])


class ProseScriptTest(unittest.TestCase):
    """Düz metinde sembole yapışık küçük parça simgedir; dipnot işareti değildir."""

    def test_superscript_on_a_symbol_becomes_unicode(self):
        self.assertEqual(_script_fixes("m", "a"), {"ma": "mᵃ"})

    def test_mark_smaller_than_the_script_ratio_is_a_footnote(self):
        self.assertEqual(_fixes_with_mark_size(SIZE * PROSE_SCRIPT_MIN_SIZE_RATIO - STEP), {})

    def test_mark_as_large_as_the_script_ratio_is_not_a_script(self):
        self.assertEqual(_fixes_with_mark_size(SIZE * SCRIPT_SIZE_RATIO), {})

    def test_mark_after_a_long_word_is_a_footnote(self):
        self.assertEqual(_script_fixes("ratio", "a"), {})

    def test_symbol_of_two_characters_takes_a_script(self):
        self.assertEqual(_script_fixes("UR", "2"), {"UR2": "UR²"})

    def test_mark_after_three_characters_is_a_footnote(self):
        self.assertEqual(_script_fixes("URL", "2"), {})

    def test_mark_after_punctuation_is_a_footnote(self):
        self.assertEqual(_script_fixes("m.", "2"), {})

    def test_blank_raised_piece_gives_no_word_fix(self):
        self.assertEqual(_script_fixes("m", " "), {})

    def test_two_scripts_in_one_sentence_stay_separate(self):
        """PyMuPDF aynı taban çizgisindeki iki simgeyi tek satırda verir: 'cᵉ and cᵃ'."""
        host = _host("c")
        first = SCRIPT.on_baseline("e", _end_of(host, SCRIPT_RISE))
        middle = BODY.at(" and c", (first.box.x1, host.box.y0))
        second = SCRIPT.on_baseline("a", _end_of(middle, SCRIPT_RISE))
        self.assertEqual(_fixes_around(host, [first, middle, second]), {"ce": "cᵉ", "ca": "cᵃ"})


def _fixes_with_gaps(*marks):
    """'In the equation, m' + simge parçaları + ' represents'; marks: (metin, soldakinden boşluk).
    Simgeler sembolün taban çizgisinden SCRIPT_RISE kadar yukarıdadır."""
    host = _host("m")
    script_baseline = host.baseline - SCRIPT_RISE
    pieces = [host]
    for text, gap in marks:
        pieces.append(SCRIPT.on_baseline(text, (pieces[-1].box.x1 + gap, script_baseline)))
    return _fixes_around(host, pieces[1:])


class ScriptGapTest(unittest.TestCase):
    """Simge sembolün hemen sağında başlar; parçaları arasındaki boşluk küçüktür."""

    def test_mark_at_the_gap_from_its_symbol_is_a_script(self):
        self.assertEqual(_fixes_with_gaps(("a", PROSE_SCRIPT_MAX_GAP)), {"ma": "mᵃ"})

    def test_mark_further_from_its_symbol_is_a_footnote(self):
        self.assertEqual(_fixes_with_gaps(("a", PROSE_SCRIPT_MAX_GAP + STEP)), {})

    def test_pieces_at_the_run_gap_are_one_script(self):
        self.assertEqual(_fixes_with_gaps(("a", 0), ("b", SCRIPT_RUN_MAX_GAP)), {"mab": "mᵃᵇ"})

    def test_pieces_further_apart_are_separate_marks(self):
        self.assertEqual(_fixes_with_gaps(("a", 0), ("b", SCRIPT_RUN_MAX_GAP + STEP)), {"ma": "mᵃ"})


class LayoutScannerTest(unittest.TestCase):
    def test_empty_page_has_nothing_to_repair(self):
        self.assertEqual(_scan(), {"page_height": PAGE_HEIGHT, "code_blocks": [], "inline_code": [],
                                   "hyphen_fixes": {}, "script_fixes": {}, "code_image_links": []})


if __name__ == "__main__":
    unittest.main()
