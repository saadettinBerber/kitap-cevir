import copy
import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from json_file import write_json
from migrate_match import TranslationFiller, Translations
from migrate_page import MigrationFinisher, Migrator, PageMigration, node_at
from page_document import PageDocument
from project import Project
from translated_pages import TranslatedPages

PAGE = 9


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


def _old_translations():
    return Translations.of_page(PageDocument(OLD_PAGE), {})


COMPLETE_DOCUMENT = {"id": "page-9", "page": PAGE, "pdf_page": PAGE, "chapter": {"num": 1, "en": "One", "tr": "Bir"},
                     "blocks": [{"type": "heading", "level": 1, "en": "Coupling"}]}


class TranslationKeyTest(unittest.TestCase):
    def test_normalize_ignores_case_quotes_tags_and_placeholders(self):
        self.assertEqual(Translations.key("The “Code” <sup>1</sup> ⟦eq-2⟧."), Translations.key('the "code" 1'))

    def test_normalize_ignores_curly_apostrophes_and_backticks(self):
        self.assertEqual(Translations.key("don’t `run`"), Translations.key("don't run"))


class TranslationsTest(unittest.TestCase):
    def test_old_units_are_found_one_by_one(self):
        translations = _old_translations()
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
        translations = Translations.of_page(PageDocument(old), {"10 x": "10^23 x"})
        self.assertEqual(translations.lookup("10^23 x"), "10^23 x")

    def test_joined_old_units_match_one_new_sentence(self):
        translations = _old_translations()
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
    def test_found_translation_is_given(self):
        self.assertEqual(TranslationFiller(_old_translations()).translation("Coupling"), "Bağlılık")

    def test_blank_unit_has_an_empty_translation(self):
        self.assertEqual(TranslationFiller(Translations([])).translation("  "), "")

    def test_numeric_cell_copies_english(self):
        self.assertEqual(TranslationFiller(Translations([])).translation("42 %"), "42 %")

    def test_numeric_cell_keeps_its_old_translation(self):
        self.assertEqual(TranslationFiller(Translations([_unit("42 %", "%42")])).translation("42 %"), "%42")

    def test_unmatched_unit_has_an_empty_translation(self):
        self.assertEqual(TranslationFiller(Translations([])).translation("Brand new."), "")

    def test_translation_missing_the_placeholder_is_not_given(self):
        filler = TranslationFiller(Translations([_unit("Loss is ⟦eq-1⟧.", "Kayıp budur.")]))
        self.assertEqual(filler.translation("Loss is ⟦eq-1⟧."), "")


class PendingTest(unittest.TestCase):
    def test_untranslated_unit_is_pending(self):
        pending = TranslationFiller(Translations([])).pending([("blocks[3]", _unit("Brand new.", ""))])
        self.assertEqual(pending, [{"path": "blocks[3]", "en": "Brand new.", "tr_hint": ""}])

    def test_translated_unit_is_not_pending(self):
        self.assertEqual(TranslationFiller(Translations([])).pending([("p", _unit("A.", "Bir."))]), [])

    def test_blank_unit_is_not_pending(self):
        self.assertEqual(TranslationFiller(Translations([])).pending([("p", _unit("  ", ""))]), [])

    def test_old_translation_missing_the_placeholder_is_the_hint(self):
        filler = TranslationFiller(Translations([_unit("Loss is ⟦eq-1⟧.", "Kayıp budur.")]))
        self.assertEqual(filler.pending([("p", _unit("Loss is ⟦eq-1⟧.", ""))])[0]["tr_hint"], "Kayıp budur.")


class SentenceMergeTest(unittest.TestCase):
    def test_new_split_sentences_are_merged_back(self):
        filler = TranslationFiller(_old_translations())
        merged = filler.merged_sentences([{"en": "Whole sentence"}, {"en": "split later."}])
        self.assertEqual(merged, [{"en": "Whole sentence split later."}])

    def test_sentence_found_alone_is_not_merged(self):
        filler = TranslationFiller(Translations([_unit("A.", "bir"), _unit("A. B.", "bir iki")]))
        merged = filler.merged_sentences([{"en": "A."}, {"en": "B."}])
        self.assertEqual([sentence["en"] for sentence in merged], ["A.", "B."])

    def test_longest_join_is_tried_first(self):
        filler = TranslationFiller(Translations([_unit("A B", "ab"), _unit("A B C", "abc")]))
        merged = filler.merged_sentences([{"en": "A"}, {"en": "B"}, {"en": "C"}])
        self.assertEqual(merged, [{"en": "A B C"}])


def _new_document():
    return {"id": "page-9", "page": PAGE, "pdf_page": PAGE,
            "chapter": {"num": 1, "en": "One", "tr": ""}, "title": _unit("", ""),
            "section": _unit("S", ""), "concepts": [], "glossary_new": [{"en": "x"}], "math": [],
            "blocks": [{"type": "heading", "level": 1, "en": "Coupling"},
                       {"type": "para", "sentences": [{"en": "First part second part."},
                                                      {"en": "Unseen sentence."}]},
                       {"type": "math", "src": "eq-1.png", "text": "x", "latex": ""},
                       {"type": "math", "src": "eq-2.png", "text": "y", "latex": ""}]}


def _migrated(document, old=OLD_PAGE):
    """(taşınmış belge, bekleyen birimler, LaTeX'i olmayan denklemler)."""
    pending = PageMigration(document, PageDocument(copy.deepcopy(old))).run({})
    return document, pending["units"], pending["latex"]


class PageMigrationTest(unittest.TestCase):
    def test_heading_translation_is_carried(self):
        document, _, _ = _migrated(_new_document())
        self.assertEqual(document["blocks"][0]["tr"], "Bağlılık")

    def test_joined_old_units_fill_a_new_sentence(self):
        document, _, _ = _migrated(_new_document())
        self.assertEqual(document["blocks"][1]["sentences"][0]["tr"], "İlk kısım ikinci kısım.")

    def test_title_section_and_cards_come_from_the_old_page(self):
        document, _, _ = _migrated(_new_document())
        self.assertEqual([document[field] for field in ("title", "section", "concepts")],
                         [OLD_PAGE["title"], OLD_PAGE["section"], OLD_PAGE["concepts"]])

    def test_field_missing_on_the_old_page_keeps_the_new_one(self):
        old = {key: value for key, value in OLD_PAGE.items() if key != "section"}
        document, _, _ = _migrated(_new_document(), old)
        self.assertEqual(document["section"], _unit("S", ""))

    def test_empty_field_of_the_old_page_still_wins(self):
        new = {**_new_document(), "concepts": [{"id": "yeni"}]}
        document, _, _ = _migrated(new, {**OLD_PAGE, "concepts": []})
        self.assertEqual(document["concepts"], [])

    def test_chapter_without_turkish_comes_from_the_old_page(self):
        document, _, _ = _migrated(_new_document())
        self.assertEqual(document["chapter"]["tr"], "Bir")

    def test_chapter_with_turkish_is_kept(self):
        new = {**_new_document(), "chapter": {"num": 1, "en": "One", "tr": "Yeni"}}
        document, _, _ = _migrated(new)
        self.assertEqual(document["chapter"]["tr"], "Yeni")

    def test_new_glossary_terms_are_cleared(self):
        document, _, _ = _migrated(_new_document())
        self.assertEqual(document["glossary_new"], [])

    def test_equation_latex_is_carried_by_its_png(self):
        document, _, _ = _migrated(_new_document())
        self.assertEqual(document["blocks"][2]["latex"], "x^2")

    def test_latex_already_in_the_new_page_is_kept(self):
        new = _new_document()
        new["blocks"][2]["latex"] = "yeni"
        document, _, _ = _migrated(new)
        self.assertEqual(document["blocks"][2]["latex"], "yeni")

    def test_display_latex_wins_over_inline_latex_of_the_same_png(self):
        old = {**OLD_PAGE, "math": [{"src": "eq-1.png", "text": "x", "latex": "satır içi"}]}
        document, _, _ = _migrated(_new_document(), old)
        self.assertEqual(document["blocks"][2]["latex"], "x^2")

    def test_unfound_sentence_is_pending(self):
        _, pending, _ = _migrated(_new_document())
        self.assertEqual([unit["path"] for unit in pending], ["blocks[1].sentences[1]"])

    def test_equation_without_latex_is_listed(self):
        _, _, latex_items = _migrated(_new_document())
        self.assertEqual(latex_items, [{"path": "blocks[3]", "src": "eq-2.png"}])

    def test_inline_equation_without_latex_is_listed(self):
        new = {**_new_document(), "math": [{"src": "eq-9.png", "text": "z", "latex": ""}]}
        _, _, latex_items = _migrated(new)
        self.assertEqual(latex_items[-1], {"path": "math[0]", "src": "eq-9.png"})


def _carried(new_blocks, *old_units):
    """(taşınmış bloklar, bekleyen birimler); eski sayfanın birimleri altyazı olarak verilir."""
    document = {"chapter": {"num": 1, "en": "One", "tr": "Bir"}, "blocks": list(new_blocks)}
    old = {"blocks": [{"type": "caption", "en": en, "tr": tr} for en, tr in old_units]}
    return document["blocks"], PageMigration(document, PageDocument(old)).run({})["units"]


def _caption(en):
    return {"type": "caption", "en": en}


class CarriedUnitTest(unittest.TestCase):
    """Birim kuralları sayfa taşıma düzeyinde sınanır."""

    def test_blank_unit_is_complete_without_a_translation(self):
        blocks, pending = _carried([_caption("  ")])
        self.assertEqual((blocks[0]["tr"], pending), ("", []))

    def test_numeric_cell_without_an_old_translation_keeps_its_english(self):
        blocks, pending = _carried([_caption("42 %")])
        self.assertEqual((blocks[0]["tr"], pending), ("42 %", []))

    def test_numeric_cell_keeps_its_old_translation(self):
        blocks, _ = _carried([_caption("42 %")], ("42 %", "%42"))
        self.assertEqual(blocks[0]["tr"], "%42")

    def test_unit_losing_its_placeholder_waits_with_the_old_translation_as_hint(self):
        blocks, pending = _carried([_caption("Loss is ⟦eq-1⟧.")], ("Loss is ⟦eq-1⟧.", "Kayıp budur."))
        self.assertEqual((blocks[0]["tr"], pending),
                         ("", [{"path": "blocks[0]", "en": "Loss is ⟦eq-1⟧.", "tr_hint": "Kayıp budur."}]))

    def test_sentences_split_from_one_old_unit_are_merged_back(self):
        para = {"type": "para", "sentences": [{"en": "Whole sentence"}, {"en": "split later."}]}
        blocks, _ = _carried([para], ("Whole sentence split later.", "Sonra bölünen tüm cümle."))
        self.assertEqual(blocks[0]["sentences"], [_unit("Whole sentence split later.", "Sonra bölünen tüm cümle.")])

    def test_pending_sentence_path_counts_merged_sentences(self):
        para = {"type": "para", "sentences": [{"en": "A"}, {"en": "B"}, {"en": "Yeni."}]}
        _, pending = _carried([para], ("A B", "ab"))
        self.assertEqual([unit["path"] for unit in pending], ["blocks[0].sentences[1]"])

    def test_pending_list_item_carries_its_item_path(self):
        items = {"type": "list", "items": [{"en": "Known."}, {"en": "Yeni."}]}
        _, pending = _carried([items], ("Known.", "Bilinen."))
        self.assertEqual([unit["path"] for unit in pending], ["blocks[0].items[1]"])

    def test_pending_table_cell_carries_its_cell_path(self):
        table = {"type": "table", "rows": [[{"en": "Name"}, {"en": "Yeni"}]]}
        _, pending = _carried([table], ("Name", "Ad"))
        self.assertEqual([unit["path"] for unit in pending], ["blocks[0].rows[0][1]"])

    def test_pending_units_keep_the_page_order(self):
        _, pending = _carried([_caption("Birinci."), _caption("İkinci.")])
        self.assertEqual([unit["path"] for unit in pending], ["blocks[0]", "blocks[1]"])


class NodePathTest(unittest.TestCase):
    def test_path_leads_to_the_pending_unit(self):
        self.assertEqual(node_at(_new_document(), "blocks[1].sentences[1]"), {"en": "Unseen sentence."})


class FakePageInputBuilder:
    """PageInputBuilder gibi; PDF yerine hazır yeni belgeyi verir."""

    def __init__(self, document):
        self._document = document

    def build(self, page, image_dir):
        return copy.deepcopy(self._document)

    def hyphen_fixes(self, pdf_page):
        return {}


class RecordingFinalizer:
    """PageFinalizer gibi; sonlandırılan çevirmen çıktılarının yollarını kaydeder."""

    def __init__(self):
        self._finalized = []

    def finalize(self, translated_path):
        self._finalized.append(translated_path)
        return {"untranslated": 0}

    def finalized(self):
        return list(self._finalized)


class MigratorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Project(self.tmp.name)
        TranslatedPages(self.project).save(PageDocument({**OLD_PAGE, "page": PAGE}))
        self.finalizer = RecordingFinalizer()

    def tearDown(self):
        self.tmp.cleanup()

    def _migrator(self, new_document):
        return Migrator(self.project, FakePageInputBuilder(new_document))

    def _apply_done(self, done):
        write_json(self.project.work_migration_file("done", PAGE), done)
        MigrationFinisher(self.project, self.finalizer).apply(PAGE)

    @staticmethod
    def _read(path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def test_migrated_page_is_written_for_finalizing(self):
        self._migrator(_new_document()).run(PAGE)
        self.assertEqual(self._read(self.project.work_output(PAGE))["blocks"][0]["tr"], "Bağlılık")

    def test_pending_units_are_written_for_the_agent(self):
        self._migrator(_new_document()).run(PAGE)
        pending = self._read(self.project.work_migration_file("pending", PAGE))
        self.assertEqual((pending["page"], len(pending["units"]), len(pending["latex"])), (PAGE, 1, 1))

    def test_complete_page_removes_an_old_pending_file(self):
        path = self.project.work_migration_file("pending", PAGE)
        os.makedirs(os.path.dirname(path))
        open(path, "w").close()
        self._migrator(COMPLETE_DOCUMENT).run(PAGE)
        self.assertFalse(os.path.exists(path))

    def test_result_counts_units_and_what_is_missing(self):
        result = self._migrator(_new_document()).run(PAGE)
        self.assertEqual(result, {"page": PAGE, "units": 3, "pending": 1, "latex": 1, "complete": False})

    def test_complete_page_is_reported_complete(self):
        self.assertTrue(self._migrator(COMPLETE_DOCUMENT).run(PAGE)["complete"])

    def test_done_answers_are_written_before_finalizing(self):
        self._migrator(_new_document()).run(PAGE)
        self._apply_done({"units": [{"path": "blocks[1].sentences[1]", "tr": "Görülmemiş cümle."}],
                          "latex": [{"path": "blocks[3]", "latex": "y^2"}]})
        document = self._read(self.project.work_output(PAGE))
        self.assertEqual((document["blocks"][1]["sentences"][1]["tr"], document["blocks"][3]["latex"]),
                         ("Görülmemiş cümle.", "y^2"))

    def test_applied_page_is_finalized(self):
        self._migrator(COMPLETE_DOCUMENT).run(PAGE)
        self._apply_done({})
        self.assertEqual(self.finalizer.finalized(), [self.project.work_output(PAGE)])


if __name__ == "__main__":
    unittest.main()
