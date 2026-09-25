import copy
import unittest

import _paths  # noqa: F401
from migrate_match import TranslationFiller, Translations
from migrate_page import Migrator, PageMigration


def _unit(en, tr):
    return {"en": en, "tr": tr}


OLD_PAGE = {
    "title": _unit("T", "B"), "section": _unit("S", "K"),
    "chapter": {"num": 1, "en": "One", "tr": "Bir"},
    "concepts": [{"id": "kart"}],
    "blocks": [
        {"type": "heading", "level": 1, "en": "Coupling", "tr": "Bağlılık"},
        {"type": "para", "sentences": [_unit("First part", "İlk kısım"), _unit("second part.", "ikinci kısım.")]},
        {"type": "para", "sentences": [_unit("Whole sentence split later.", "Sonra bölünen tüm cümle.")]},
        {"type": "math", "src": "eq-1.png", "text": "x", "latex": "x^2"},
    ],
}


def _pending(filler):
    return filler.pending


class TranslationKeyTest(unittest.TestCase):
    def test_normalize_ignores_case_quotes_tags_and_placeholders(self):
        self.assertEqual(Translations.key("The “Code” <sup>1</sup> ⟦eq-2⟧."), Translations.key('the "code" 1'))

    def test_normalize_ignores_curly_apostrophes_and_backticks(self):
        self.assertEqual(Translations.key("don’t `run`"), Translations.key("don't run"))


class TranslationsTest(unittest.TestCase):
    def test_old_units_are_found_one_by_one(self):
        translations = Translations.of_page(OLD_PAGE, {})
        self.assertEqual([translations.lookup_single(en) for en in ("Coupling", "First part", "second part.")],
                         ["Bağlılık", "İlk kısım", "ikinci kısım."])

    def test_first_translation_of_a_repeated_unit_wins(self):
        translations = Translations([_unit("A.", "bir"), _unit("A.", "iki")])
        self.assertEqual(translations.lookup_single("A."), "bir")

    def test_first_translation_of_a_repeated_join_wins(self):
        translations = Translations([_unit("A", "1"), _unit("B", "2"), _unit("A", "3"), _unit("B", "4")])
        self.assertEqual(translations.lookup("A B"), "1 2")

    def test_fixes_apply_to_both_sides(self):
        old = {"blocks": [{"type": "caption", "en": "10 x", "tr": "10 x"}]}
        translations = Translations.of_page(old, {"10 x": "10^23 x"})
        self.assertEqual(translations.lookup("10^23 x"), "10^23 x")

    def test_joined_old_units_match_one_new_sentence(self):
        translations = Translations.of_page(OLD_PAGE, {})
        self.assertEqual(translations.lookup("First part second part."), "İlk kısım ikinci kısım.")

    def test_up_to_four_old_units_join(self):
        translations = Translations([_unit(letter, letter.lower()) for letter in "ABCD"])
        self.assertEqual(translations.lookup("A B C D"), "a b c d")

    def test_five_old_units_do_not_join(self):
        translations = Translations([_unit(letter, letter.lower()) for letter in "ABCDE"])
        self.assertEqual(translations.lookup("A B C D E"), "")

    def test_single_unit_wins_over_a_join(self):
        translations = Translations([_unit("A B", "tek"), _unit("A", "1"), _unit("B", "2")])
        self.assertEqual(translations.lookup("A B"), "tek")

    def test_text_without_words_has_no_translation(self):
        self.assertEqual(Translations([_unit(" .", "nokta")]).lookup("."), "")


class TranslationFillerTest(unittest.TestCase):
    def test_found_translation_is_written(self):
        unit, filler = {"en": "Coupling"}, TranslationFiller(Translations.of_page(OLD_PAGE, {}))
        filler.fill_unit(unit, "p")
        self.assertEqual(unit["tr"], "Bağlılık")

    def test_blank_unit_gets_an_empty_translation(self):
        unit, filler = {"en": "  "}, TranslationFiller(Translations([]))
        filler.fill_unit(unit, "p")
        self.assertEqual((unit["tr"], _pending(filler)), ("", []))

    def test_numeric_cell_copies_english(self):
        unit, filler = {"en": "42 %"}, TranslationFiller(Translations([]))
        filler.fill_unit(unit, "p")
        self.assertEqual((unit["tr"], _pending(filler)), ("42 %", []))

    def test_unmatched_unit_goes_to_pending(self):
        unit, filler = {"en": "Brand new."}, TranslationFiller(Translations([]))
        filler.fill_unit(unit, "blocks[3]")
        self.assertEqual((unit["tr"], _pending(filler)),
                         ("", [{"path": "blocks[3]", "en": "Brand new.", "tr_hint": ""}]))

    def test_translation_missing_placeholder_goes_to_pending(self):
        filler = TranslationFiller(Translations([_unit("Loss is ⟦eq-1⟧.", "Kayıp budur.")]))
        filler.fill_unit({"en": "Loss is ⟦eq-1⟧."}, "p")
        self.assertEqual(_pending(filler)[0]["tr_hint"], "Kayıp budur.")


class SentenceMergeTest(unittest.TestCase):
    def test_new_split_sentences_are_merged_back(self):
        filler = TranslationFiller(Translations.of_page(OLD_PAGE, {}))
        merged = filler.fill_sentences([{"en": "Whole sentence"}, {"en": "split later."}], "blocks[0]")
        self.assertEqual(merged, [_unit("Whole sentence split later.", "Sonra bölünen tüm cümle.")])

    def test_sentence_found_alone_is_not_merged(self):
        filler = TranslationFiller(Translations([_unit("A.", "bir"), _unit("A. B.", "bir iki")]))
        merged = filler.fill_sentences([{"en": "A."}, {"en": "B."}], "blocks[0]")
        self.assertEqual([sentence["en"] for sentence in merged], ["A.", "B."])

    def test_longest_join_is_tried_first(self):
        filler = TranslationFiller(Translations([_unit("A B", "ab"), _unit("A B C", "abc")]))
        merged = filler.fill_sentences([{"en": "A"}, {"en": "B"}, {"en": "C"}], "blocks[0]")
        self.assertEqual(merged, [_unit("A B C", "abc")])

    def test_merged_sentences_are_numbered_again(self):
        filler = TranslationFiller(Translations([_unit("A B", "ab")]))
        filler.fill_sentences([{"en": "A"}, {"en": "B"}, {"en": "Yeni."}], "blocks[0]")
        self.assertEqual(_pending(filler)[0]["path"], "blocks[0].sentences[1]")


class MigrateTest(unittest.TestCase):
    def _new_document(self):
        return {"chapter": {"num": 1, "en": "One", "tr": ""}, "title": _unit("", ""),
                "section": _unit("S", ""), "concepts": [],
                "blocks": [{"type": "heading", "level": 1, "en": "Coupling"},
                           {"type": "para", "sentences": [{"en": "First part second part."},
                                                          {"en": "Unseen sentence."}]},
                           {"type": "math", "src": "eq-1.png", "text": "x", "latex": ""},
                           {"type": "math", "src": "eq-2.png", "text": "y", "latex": ""}]}

    def test_carries_translations_fields_and_latex(self):
        document = self._new_document()
        pending, latex_items = PageMigration(document, copy.deepcopy(OLD_PAGE)).run({})
        self.assertEqual(document["blocks"][0]["tr"], "Bağlılık")
        self.assertEqual(document["blocks"][1]["sentences"][0]["tr"], "İlk kısım ikinci kısım.")
        self.assertEqual(document["blocks"][2]["latex"], "x^2")
        self.assertEqual((document["title"], document["concepts"]), (OLD_PAGE["title"], OLD_PAGE["concepts"]))
        self.assertEqual(document["chapter"]["tr"], "Bir")
        self.assertEqual([p["path"] for p in pending], ["blocks[1].sentences[1]"])
        self.assertEqual(latex_items, [{"path": "blocks[3]", "src": "eq-2.png"}])

    def test_resolve_follows_pending_paths(self):
        document = self._new_document()
        self.assertEqual(Migrator._resolve(document, "blocks[1].sentences[1]"), {"en": "Unseen sentence."})


if __name__ == "__main__":
    unittest.main()
