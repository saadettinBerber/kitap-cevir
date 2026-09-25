import unittest

import _paths  # noqa: F401
from page_blocks import Block
from page_document import PageDocument


def _unit(en, tr=""):
    return {"en": en, "tr": tr}


PARA = {"type": "para", "sentences": [_unit("One.", "Bir."), _unit("Two.", "İki.")]}
TABLE = {"type": "table", "rows": [[_unit("a"), _unit("b")], [_unit("c"), _unit("d")]]}
CODE = {"type": "code", "lang": "python", "code": "x = 1"}


class _RecordingFiller:
    def __init__(self):
        self.paths = []

    def fill_unit(self, unit, path):
        self.paths.append(path)

    def fill_sentences(self, sentences, path):
        self.paths.append(f"{path}:sentences")
        return sentences[:1]


class _NamingVisitor:
    """Her visit_* çağrısı kendi adını döner; accept'in hangi metoda gittiği görünür."""

    def __getattr__(self, name):
        return lambda block: name


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

    def test_list_fill_uses_item_paths(self):
        filler = _RecordingFiller()
        Block.of({"type": "list", "items": [_unit("x"), _unit("y")]}).fill(filler, "blocks[2]")
        self.assertEqual(filler.paths, ["blocks[2].items[0]", "blocks[2].items[1]"])

    def test_para_fill_replaces_sentences_with_merged_ones(self):
        para = {"type": "para", "sentences": [_unit("a"), _unit("b")]}
        Block.of(para).fill(_RecordingFiller(), "blocks[0]")
        self.assertEqual(para["sentences"], [_unit("a")])

    def test_card_unit_joins_text_and_keeps_code_as_is(self):
        self.assertEqual(Block.of(PARA).card_unit(), {"type": "para", "en": "One. Two.", "tr": "Bir. İki."})
        self.assertEqual(Block.of(CODE).card_unit(), {"type": "code", "code": "x = 1"})
        self.assertEqual(Block.of({"type": "image", "src": "a.png"}).card_unit(), {})

    def test_anchor_text_of_para_table_and_code(self):
        self.assertEqual(Block.of(PARA).anchor_text(), "One. Two.")
        self.assertEqual(Block.of(TABLE).anchor_text(), "")
        self.assertEqual(Block.of(CODE).anchor_text(), "")

    def test_only_headings_lead_the_page(self):
        leads = {kind: Block.of({"type": kind}).leads_page() for kind in ("chapter", "heading", "caption")}
        self.assertEqual(leads, {"chapter": True, "heading": True, "caption": False})


class PageQueriesTest(unittest.TestCase):
    PAGE = {"blocks": [PARA, {"type": "image", "src": "a.png"},
                       {"type": "math", "src": "eq-1.png", "latex": ""}, PARA],
            "math": [{"id": "eq-2", "src": "eq-2.png", "latex": ""}]}

    def test_summary_counts_block_kinds_in_order(self):
        self.assertEqual(PageDocument(self.PAGE).block_summary(), "para:2, image:1, math:1")

    def test_media_sources_include_inline_equations(self):
        self.assertEqual(PageDocument(self.PAGE).media_sources(), ["a.png", "eq-1.png", "eq-2.png"])

    def test_equation_count_adds_display_and_inline(self):
        self.assertEqual(PageDocument(self.PAGE).equation_count(), 2)

    def test_page_with_only_images_is_blank(self):
        self.assertTrue(PageDocument({"blocks": [{"type": "image", "src": "a.png"}]}).is_blank())
        self.assertFalse(PageDocument(self.PAGE).is_blank())


if __name__ == "__main__":
    unittest.main()
