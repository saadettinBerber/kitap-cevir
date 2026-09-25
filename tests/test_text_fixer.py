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


def _rich(text, *tokens):
    return TextFixer({"hyphen_fixes": {}, "inline_code": list(tokens)}).rich(text)


class InlineCodeTest(unittest.TestCase):
    """Satır içi kod parçaları ters tırnakla işaretlenir; uzun parça önce gelir."""

    def test_token_is_marked(self):
        self.assertEqual(_rich("call getUser now", "getUser"), "call `getUser` now")

    def test_token_inside_a_longer_word_is_not_marked(self):
        self.assertEqual(_rich("call getUsers now", "getUser"), "call getUsers now")

    def test_token_inside_a_longer_marked_token_is_not_marked_again(self):
        self.assertEqual(_rich("call getUser() now", "getUser", "getUser()"), "call `getUser()` now")


if __name__ == "__main__":
    unittest.main()
