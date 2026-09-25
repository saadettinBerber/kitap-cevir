import unittest

import _paths  # noqa: F401
from book_settings import CARD_KINDS
from concept_check import CardChecker, kind_rules

SPEC = {"kinds": ["explain", "contrast", "tradeoff", "code"], "code_langs": ["python"],
        "code_comment_lang": "en"}


def _pair(text="x"):
    return {"en": text, "tr": text}


def _card(card_id, kind, **fields):
    return {"id": card_id, "kind": kind, "title": _pair(), "summary": _pair(), "tip": _pair(), **fields}


def _option(name):
    return {"name": _pair(name), "gains": _pair(), "costs": _pair()}


def _code(lang="python"):
    return {"lang": lang, "code": "x = 1", "why": _pair()}


EXPLAIN = _card("tanim", "explain")
TRADEOFF = _card("secim", "tradeoff", options=[_option("A"), _option("B")])
CONTRAST = _card("karsit", "contrast", bad={"text": _pair(), "why": _pair()},
                 good={"text": _pair(), "why": _pair()})
CODE = _card("kod", "code", bad=_code(), good=_code("py"))


class CardProblemsTest(unittest.TestCase):
    def test_valid_cards_of_every_kind(self):
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, TRADEOFF, CONTRAST, CODE]), [])

    def test_card_count_is_bounded(self):
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN]), ["kart sayısı 1 (2-4 olmalı)"])

    def test_kind_must_be_allowed(self):
        spec = {**SPEC, "kinds": ["explain", "tradeoff"]}
        problems = CardChecker(spec).problems([EXPLAIN, CODE])
        self.assertEqual(problems, ["kod: tür 'code' bu kitapta izinli değil (explain, tradeoff)"])

    def test_missing_translation_is_reported(self):
        card = _card("bos", "explain", tip={"en": "x", "tr": " "})
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["bos: tip.tr boş"])

    def test_code_language_must_be_allowed(self):
        card = _card("java", "code", bad=_code("java"), good=_code())
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]),
                         ["java: bad.lang 'java' izinli değil (python)"])

    def test_tradeoff_needs_two_or_three_options(self):
        card = _card("tek", "tradeoff", options=[_option("A")])
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["tek: options sayısı 1 (2-3 olmalı)"])

    def test_explain_card_carries_no_samples(self):
        card = _card("fazla", "explain", bad={"text": _pair()})
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["fazla: explain kartında `bad` olmamalı"])

    def test_contrast_side_needs_text_and_why(self):
        card = _card("yarim", "contrast", bad={}, good={"text": _pair(), "why": _pair()})
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["yarim: bad.text yok", "yarim: bad.why yok"])

    def test_duplicate_ids_are_reported(self):
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, EXPLAIN]), ["tanim: id tekrar ediyor"])


class KindRulesTest(unittest.TestCase):
    def test_every_card_kind_has_rules(self):
        self.assertEqual(set(kind_rules(["python"])), set(CARD_KINDS))


if __name__ == "__main__":
    unittest.main()
