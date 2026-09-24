import os
import tempfile
import unittest

import fitz

import _paths  # noqa: F401
from extraction.text_layer.code_lines import CodeFont, PageLineReader
from extraction.text_layer.script_marks import ScriptFixes
from extraction.settings import DEFAULT_EXTRACTION
from extraction.text_fixer import TextFixer

BODY_SIZE = 10.5
SCRIPT_SIZE = 8.0          # gövdenin %76'sı: dipnot işaretinden büyük, simge boyutunda
BASELINE = 100
SCRIPT_RISE = 4.6
LEFT = 72


def _write(page, text, x, baseline, size=BODY_SIZE):
    page.insert_text(fitz.Point(x, baseline), text, fontsize=size, fontname="helvetica")
    return x + fitz.get_text_length(text, fontsize=size, fontname="helvetica")


def _sentence_with_script(page, baseline, symbol, script):
    """'In the equation, <symbol>' + yukarı kaydırılmış <script> + ' represents'."""
    cursor = _write(page, f"In the equation, {symbol}", LEFT, baseline)
    cursor = _write(page, script, cursor, baseline - SCRIPT_RISE, SCRIPT_SIZE)
    _write(page, " represents the ratio.", cursor, baseline)


def _fixes_for(*sentences):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "p.pdf")
        document = fitz.open()
        page = document.new_page()
        for index, (symbol, script) in enumerate(sentences):
            _sentence_with_script(page, BASELINE + index * 40, symbol, script)
        document.save(path)
        document.close()
        document = fitz.open(path)
        try:
            lines = PageLineReader(CodeFont(DEFAULT_EXTRACTION)).read(document[0])
            return ScriptFixes(lines).for_prose()
        finally:
            document.close()


class ProseScriptFixTest(unittest.TestCase):
    """ODL üst simgeyi düz karaktere düşürür ('ma'); düzeltme sözlüğü bunu onarır."""

    def test_superscript_letter_becomes_unicode(self):
        self.assertEqual(_fixes_for(("m", "a")), {"ma": "mᵃ"})

    def test_superscript_digit_becomes_unicode(self):
        self.assertEqual(_fixes_for(("UR", "2")), {"UR2": "UR²"})

    def test_unmapped_character_falls_back_to_marker(self):
        self.assertEqual(_fixes_for(("m", "Q")), {"mQ": "m^Q"})

    def test_two_scripts_on_one_baseline_stay_separate(self):
        self.assertEqual(_fixes_for(("c", "e"), ("c", "a")), {"ce": "cᵉ", "ca": "cᵃ"})

    def test_marker_after_a_word_is_a_footnote_reference(self):
        self.assertEqual(_fixes_for(("Photos.", "22")), {})


class WordBoundaryTest(unittest.TestCase):
    """'ma' -> 'mᵃ' düzeltmesi başka kelimenin içini bozmamalı."""

    def _fixer(self):
        return TextFixer({"hyphen_fixes": {}, "inline_code": [], "script_fixes": {"ma": "mᵃ"}})

    def test_whole_word_is_fixed(self):
        self.assertEqual(self._fixer().plain("In the equation, ma represents"),
                         "In the equation, mᵃ represents")

    def test_word_followed_by_punctuation_is_fixed(self):
        self.assertEqual(self._fixer().plain("the ratio of ma, mc"), "the ratio of mᵃ, mc")

    def test_other_words_are_untouched(self):
        self.assertEqual(self._fixer().plain("format and summary"), "format and summary")

    def test_missing_script_fixes_key_is_allowed(self):
        fixer = TextFixer({"hyphen_fixes": {}, "inline_code": []})
        self.assertEqual(fixer.plain("format"), "format")


if __name__ == "__main__":
    unittest.main()
