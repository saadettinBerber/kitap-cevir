import unittest

import _paths  # noqa: F401
from book_settings import CARD_KINDS
from concept_cards import Card
from concept_check import CardChecker, CardRules

SPEC = {"kinds": ["explain", "contrast", "tradeoff", "code"], "code_langs": ["python"],
        "code_comment_lang": "en"}


def _pair(text="x"):
    return {"en": text, "tr": text}


def _card(kind, **fields):
    """Kimlik `id=` ile verilir; verilmezse kart kimliksizdir."""
    return {"kind": kind, "title": _pair(), "summary": _pair(), "tip": _pair(), **fields}


def _option(name):
    return {"name": _pair(name), "gains": _pair(), "costs": _pair()}


def _code(lang="python"):
    return {"lang": lang, "code": "x = 1", "why": _pair()}


EXPLAIN = _card("explain", id="tanim")
TRADEOFF = _card("tradeoff", id="secim", options=[_option("A"), _option("B")])
CONTRAST = _card("contrast", id="karsit", bad={"text": _pair(), "why": _pair()},
                 good={"text": _pair(), "why": _pair()})
CODE = _card("code", id="kod", bad=_code(), good=_code("py"))


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
        card = _card("explain", id="bos", tip={"en": "x", "tr": " "})
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["bos: tip.tr boş"])

    def test_code_language_must_be_allowed(self):
        card = _card("code", id="java", bad=_code("java"), good=_code())
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]),
                         ["java: bad.lang 'java' izinli değil (python)"])

    def test_tradeoff_needs_two_or_three_options(self):
        card = _card("tradeoff", id="tek", options=[_option("A")])
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["tek: options sayısı 1 (2-3 olmalı)"])

    def test_every_option_needs_gains(self):
        card = _card("tradeoff", id="eksik", options=[_option("A"), {"name": _pair("B"), "costs": _pair()}])
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["eksik: options[2].gains yok"])

    def test_explain_card_carries_no_samples(self):
        card = _card("explain", id="fazla", bad={"text": _pair()})
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["fazla: explain kartında `bad` olmamalı"])

    def test_contrast_side_needs_text_and_why(self):
        card = _card("contrast", id="yarim", bad={}, good={"text": _pair(), "why": _pair()})
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["yarim: bad.text yok", "yarim: bad.why yok"])

    def test_card_without_id_is_named_by_its_position(self):
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, _card("explain")]), ["#2: id yok"])

    def test_three_options_are_allowed(self):
        card = _card("tradeoff", id="uc", options=[_option("A"), _option("B"), _option("C")])
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), [])

    def test_four_options_are_too_many(self):
        card = _card("tradeoff", id="dort", options=[_option(name) for name in "ABCD"])
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), ["dort: options sayısı 4 (2-3 olmalı)"])

    def test_five_cards_are_too_many(self):
        cards = [EXPLAIN, TRADEOFF, CONTRAST, CODE, _card("explain", id="fazla")]
        self.assertEqual(CardChecker(SPEC).problems(cards), ["kart sayısı 5 (2-4 olmalı)"])

    def test_contrast_side_with_code_needs_no_text(self):
        card = _card("contrast", id="kodlu", bad=_code(), good={"text": _pair(), "why": _pair()})
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, card]), [])

    def test_duplicate_ids_are_reported(self):
        self.assertEqual(CardChecker(SPEC).problems([EXPLAIN, EXPLAIN]), ["tanim: id tekrar ediyor"])


class CardRulesTest(unittest.TestCase):
    def test_every_card_kind_has_rules(self):
        rules = CardRules(SPEC["code_langs"])
        self.assertTrue(all(isinstance(Card.of({"kind": kind}).accept(rules), list) for kind in CARD_KINDS))


if __name__ == "__main__":
    unittest.main()
