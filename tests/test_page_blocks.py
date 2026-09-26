import unittest

import _paths  # noqa: F401
from page_blocks import Block
from page_document import PageDocument


def _unit(en, tr=""):
    return {"en": en, "tr": tr}


PARA = {"type": "para", "sentences": [_unit("One.", "Bir."), _unit("Two.", "İki.")]}
TABLE = {"type": "table", "rows": [[_unit("a"), _unit("b")], [_unit("c"), _unit("d")]]}
CODE = {"type": "code", "lang": "python", "code": "x = 1"}


class _UpperFiller:
    """TranslationFiller gibi; çeviri İngilizcenin büyük harflisidir, cümleleri ilkine indirir."""

    def translation(self, en):
        return en.upper()

    def merged_sentences(self, sentences):
        return sentences[:1]


class _NamingVisitor:
    """Her visit_* çağrısı kendi adını döner; accept'in hangi metoda gittiği görünür."""

    def __getattr__(self, name):
        return lambda data: name


class AcceptTest(unittest.TestCase):
    def test_each_block_type_visits_its_own_method(self):
        expected = {"caption": "visit_text_unit", "footnote": "visit_text_unit", "chapter": "visit_chapter",
                    "heading": "visit_heading", "para": "visit_para",
                    "list": "visit_list", "table": "visit_table", "code": "visit_code",
                    "image": "visit_image", "math": "visit_math", "yeni": "visit_unknown",
                    "html": "visit_unknown"}
        visited = {kind: Block.of({"type": kind}).accept(_NamingVisitor()) for kind in expected}
        self.assertEqual(visited, expected)


class BlockTest(unittest.TestCase):
    def test_table_units_carry_their_cell_paths(self):
        self.assertEqual([path for path, _ in Block.of(TABLE).unit_paths()],
                         [".rows[0][0]", ".rows[0][1]", ".rows[1][0]", ".rows[1][1]"])

    def test_text_block_is_its_own_unit(self):
        caption = {"type": "caption", "en": "Figure 1", "tr": "Şekil 1"}
        self.assertEqual(Block.of(caption).units(), [caption])

    def test_media_and_unknown_blocks_have_no_units(self):
        for data in ({"type": "image", "src": "a.png"}, {"type": "yeni"}):
            self.assertEqual(Block.of(data).units(), [], data["type"])

    def test_fill_writes_the_translation_of_every_unit(self):
        items = {"type": "list", "items": [_unit("x"), _unit("y")]}
        Block.of(items).fill(_UpperFiller())
        self.assertEqual(items["items"], [_unit("x", "X"), _unit("y", "Y")])

    def test_para_fill_replaces_sentences_with_merged_ones(self):
        para = {"type": "para", "sentences": [_unit("a"), _unit("b")]}
        Block.of(para).fill(_UpperFiller())
        self.assertEqual([sentence["en"] for sentence in para["sentences"]], ["a"])

    def test_para_fill_translates_the_merged_sentences(self):
        para = {"type": "para", "sentences": [_unit("a"), _unit("b")]}
        Block.of(para).fill(_UpperFiller())
        self.assertEqual(para["sentences"][0]["tr"], "A")

    def test_card_unit_joins_text(self):
        self.assertEqual(Block.of(PARA).card_unit(), {"type": "para", "en": "One. Two.", "tr": "Bir. İki."})

    def test_card_unit_keeps_code_as_is(self):
        self.assertEqual(Block.of(CODE).card_unit(), {"type": "code", "code": "x = 1"})

    def test_block_without_text_has_no_card_unit(self):
        self.assertEqual(Block.of({"type": "image", "src": "a.png"}).card_unit(), {})

    def test_para_anchor_text_joins_its_sentences(self):
        self.assertEqual(Block.of(PARA).anchor_text(), "One. Two.")

    def test_list_anchor_text_joins_its_items(self):
        self.assertEqual(Block.of({"type": "list", "items": [_unit("x"), _unit("y")]}).anchor_text(), "x y")

    def test_table_has_no_anchor_text(self):
        self.assertEqual(Block.of(TABLE).anchor_text(), "")

    def test_code_has_no_anchor_text(self):
        self.assertEqual(Block.of(CODE).anchor_text(), "")

    def test_only_headings_lead_the_page(self):
        leads = {kind: Block.of({"type": kind}).leads_page() for kind in ("chapter", "heading", "caption")}
        self.assertEqual(leads, {"chapter": True, "heading": True, "caption": False})


class PageQueriesTest(unittest.TestCase):
    PAGE = {"blocks": [PARA, {"type": "image", "src": "a.png"},
                       {"type": "math", "src": "eq-1.png", "latex": ""}, PARA],
            "math": [{"id": "eq-2", "src": "eq-2.png", "latex": ""}]}

    def test_json_is_a_copy_of_the_page(self):
        document = PageDocument(self.PAGE)
        document.as_json()["blocks"].clear()
        self.assertEqual(document.as_json(), self.PAGE)

    def test_unit_paths_start_at_the_page(self):
        [(first_path, _), *_] = PageDocument({"blocks": [CODE, TABLE]}).unit_paths()
        self.assertEqual(first_path, "blocks[1].rows[0][0]")

    def test_summary_counts_block_kinds_in_order(self):
        self.assertEqual(PageDocument(self.PAGE).block_summary(), "para:2, image:1, math:1")

    def test_media_sources_include_inline_equations(self):
        self.assertEqual(PageDocument(self.PAGE).media_sources(), ["a.png", "eq-1.png", "eq-2.png"])

    def test_equation_count_adds_display_and_inline(self):
        self.assertEqual(PageDocument(self.PAGE).equation_count(), 2)

    def test_page_with_only_images_is_blank(self):
        self.assertTrue(PageDocument({"blocks": [{"type": "image", "src": "a.png"}]}).is_blank())

    def test_page_with_text_is_not_blank(self):
        self.assertFalse(PageDocument(self.PAGE).is_blank())


if __name__ == "__main__":
    unittest.main()
