import unittest

import _paths  # noqa: F401
from extraction.text_fixer import TextFixer


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
