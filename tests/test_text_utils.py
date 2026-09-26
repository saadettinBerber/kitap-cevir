import unittest

import _paths  # noqa: F401
from extraction.text_utils import clean_ligatures, is_numeric_only, normalize_spaces, split_sentences, strip_list_marker


class SplitSentencesTest(unittest.TestCase):
    def test_splits_on_terminal_punctuation(self):
        self.assertEqual(split_sentences("First one. Second one! Third?"),
                         ["First one.", "Second one!", "Third?"])

    def test_keeps_abbreviations_together(self):
        self.assertEqual(split_sentences("Use tools, e.g. linters. Then ship."),
                         ["Use tools, e.g. linters.", "Then ship."])

    def test_abbreviation_before_a_capital_is_not_a_boundary(self):
        self.assertEqual(split_sentences("Ask Dr. Smith today. Then go."), ["Ask Dr. Smith today.", "Then go."])

    def test_keeps_initials_together(self):
        self.assertEqual(split_sentences("Written by Robert C. Martin. Read it."),
                         ["Written by Robert C. Martin.", "Read it."])


class HelpersTest(unittest.TestCase):
    def test_ligatures_are_expanded(self):
        self.assertEqual(clean_ligatures("ﬁle ﬂow"), "file flow")

    def test_bullet_marker_is_stripped(self):
        self.assertEqual(strip_list_marker("• item"), "item")

    def test_number_marker_is_stripped(self):
        self.assertEqual(strip_list_marker("3) item"), "item")

    def test_spaces_are_collapsed_and_trimmed(self):
        self.assertEqual(normalize_spaces("  a \n\t b "), "a b")

    def test_digits_with_separators_are_numeric_only(self):
        self.assertTrue(is_numeric_only("1,024.5 %"))

    def test_digits_beside_a_word_are_not_numeric_only(self):
        self.assertFalse(is_numeric_only("42 items"))


if __name__ == "__main__":
    unittest.main()
