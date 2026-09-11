import unittest

import _paths  # noqa: F401
from text_utils import clean_ligatures, split_sentences, strip_list_marker


class SplitSentencesTest(unittest.TestCase):
    def test_splits_on_terminal_punctuation(self):
        self.assertEqual(split_sentences("First one. Second one! Third?"),
                         ["First one.", "Second one!", "Third?"])

    def test_keeps_abbreviations_together(self):
        self.assertEqual(split_sentences("Use tools, e.g. linters. Then ship."),
                         ["Use tools, e.g. linters.", "Then ship."])

    def test_keeps_initials_together(self):
        self.assertEqual(split_sentences("Written by Robert C. Martin. Read it."),
                         ["Written by Robert C. Martin.", "Read it."])


class HelpersTest(unittest.TestCase):
    def test_ligatures_are_expanded(self):
        self.assertEqual(clean_ligatures("ﬁle ﬂow"), "file flow")

    def test_list_marker_is_stripped(self):
        self.assertEqual(strip_list_marker("• item"), "item")
        self.assertEqual(strip_list_marker("3) item"), "item")


if __name__ == "__main__":
    unittest.main()
