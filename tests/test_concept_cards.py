import unittest

import _paths  # noqa: F401
from concept_cards import CARD_KINDS, Card

TEXT = {"en": "x", "tr": "x"}


class DeclaredKindTest(unittest.TestCase):
    def test_declared_kind_wins_over_content(self):
        self.assertEqual(Card.of({"kind": "tradeoff", "bad": {"code": "x"}}).kind(), "tradeoff")

    def test_unknown_declared_kind_is_kept(self):
        self.assertEqual(Card.of({"kind": "quiz"}).kind(), "quiz")


class InferredKindTest(unittest.TestCase):
    def test_options_make_a_tradeoff(self):
        self.assertEqual(Card.of({"options": []}).kind(), "tradeoff")

    def test_code_sample_makes_a_code_card(self):
        self.assertEqual(Card.of({"bad": {"code": "x"}}).kind(), "code")

    def test_text_sample_makes_a_contrast(self):
        self.assertEqual(Card.of({"bad": {"text": TEXT}}).kind(), "contrast")

    def test_card_without_samples_explains(self):
        self.assertEqual(Card.of({"summary": TEXT}).kind(), "explain")



class CardKindsTest(unittest.TestCase):
    def test_every_kind_has_its_own_class(self):
        self.assertNotIn(Card, [type(Card.of({"kind": kind})) for kind in CARD_KINDS])

    def test_unknown_kind_is_not_a_card_kind(self):
        self.assertIs(type(Card.of({"kind": "quiz"})), Card)


if __name__ == "__main__":
    unittest.main()
