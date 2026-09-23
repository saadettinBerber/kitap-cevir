import copy
import unittest

import _paths  # noqa: F401
from migrate_match import Translations, apply_fixes, fill_sentences, fill_unit, normalize, old_units
from migrate_page import _resolve, migrate


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


class MatchTest(unittest.TestCase):
    def test_normalize_ignores_case_quotes_tags_and_placeholders(self):
        self.assertEqual(normalize("The “Code” <sup>1</sup> ⟦eq-2⟧."), normalize('the "code" 1'))

    def test_old_units_flatten_in_page_order(self):
        self.assertEqual([u["en"] for u in old_units(OLD_PAGE["blocks"])],
                         ["Coupling", "First part", "second part.", "Whole sentence split later."])

    def test_apply_fixes_updates_both_sides(self):
        units = apply_fixes([_unit("10 x", "10 x")], {"10 x": "10^23 x"})
        self.assertEqual(units, [_unit("10^23 x", "10^23 x")])

    def test_joined_old_units_match_one_new_sentence(self):
        translations = Translations(old_units(OLD_PAGE["blocks"]))
        self.assertEqual(translations.lookup("First part second part."), "İlk kısım ikinci kısım.")

    def test_new_split_sentences_are_merged_back(self):
        translations = Translations(old_units(OLD_PAGE["blocks"]))
        sentences = [{"en": "Whole sentence"}, {"en": "split later."}]
        merged = fill_sentences(sentences, translations, [], "blocks[0]")
        self.assertEqual(merged, [_unit("Whole sentence split later.", "Sonra bölünen tüm cümle.")])

    def test_numeric_cell_copies_english(self):
        unit, pending = {"en": "42 %"}, []
        self.assertTrue(fill_unit(unit, Translations([]), pending, "p"))
        self.assertEqual((unit["tr"], pending), ("42 %", []))

    def test_unmatched_unit_goes_to_pending(self):
        unit, pending = {"en": "Brand new."}, []
        self.assertFalse(fill_unit(unit, Translations([]), pending, "blocks[3]"))
        self.assertEqual(pending, [{"path": "blocks[3]", "en": "Brand new.", "tr_hint": ""}])

    def test_translation_missing_placeholder_goes_to_pending(self):
        translations = Translations([_unit("Loss is ⟦eq-1⟧.", "Kayıp budur.")])
        unit, pending = {"en": "Loss is ⟦eq-1⟧."}, []
        self.assertFalse(fill_unit(unit, translations, pending, "p"))
        self.assertEqual(pending[0]["tr_hint"], "Kayıp budur.")


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
        pending, latex_items = migrate(document, copy.deepcopy(OLD_PAGE), {})
        self.assertEqual(document["blocks"][0]["tr"], "Bağlılık")
        self.assertEqual(document["blocks"][1]["sentences"][0]["tr"], "İlk kısım ikinci kısım.")
        self.assertEqual(document["blocks"][2]["latex"], "x^2")
        self.assertEqual((document["title"], document["concepts"]), (OLD_PAGE["title"], OLD_PAGE["concepts"]))
        self.assertEqual(document["chapter"]["tr"], "Bir")
        self.assertEqual([p["path"] for p in pending], ["blocks[1].sentences[1]"])
        self.assertEqual(latex_items, [{"path": "blocks[3]", "src": "eq-2.png"}])

    def test_resolve_follows_pending_paths(self):
        document = self._new_document()
        self.assertEqual(_resolve(document, "blocks[1].sentences[1]"), {"en": "Unseen sentence."})


if __name__ == "__main__":
    unittest.main()
