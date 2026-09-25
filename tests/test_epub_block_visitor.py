import unittest

import _paths  # noqa: F401
from epub.block_visitor import EpubBlockVisitor, image_href
from epub.fragments import Heading, ParaPassage, PassageList
from page_document import PageDocument


def _page(*blocks, math=()):
    return PageDocument({"page": 12, "blocks": list(blocks), "math": list(math)})


def _fragments(*blocks, math=()):
    return EpubBlockVisitor(_page(*blocks, math=math)).fragments()


def _only(*blocks, math=()):
    [fragment] = _fragments(*blocks, math=math)
    return fragment


def _para(*sentences, style=None):
    block = {"type": "para", "sentences": [{"en": en, "tr": tr} for en, tr in sentences]}
    return {**block, "style": style} if style else block


class TextBlockTest(unittest.TestCase):
    def test_para_joins_sentences_in_both_languages(self):
        passage = _only(_para(("One.", "Bir."), ("Two.", "İki.")))
        self.assertEqual((passage.tr_html, passage.en_html), ("Bir. İki.", "One. Two."))

    def test_para_is_a_para_passage(self):
        self.assertIsInstance(_only(_para(("One.", "Bir."))), ParaPassage)

    def test_para_style_joins_its_class(self):
        self.assertEqual(_only(_para(("A.", "B."), style="quote")).css_class, "para quote")

    def test_caption_class_is_its_block_type(self):
        self.assertEqual(_only({"type": "caption", "en": "Figure", "tr": "Şekil"}).css_class, "caption")

    def test_list_keeps_order_and_items(self):
        fragment = _only({"type": "list", "ordered": True, "items": [{"en": "a", "tr": "b"}]})
        self.assertIsInstance(fragment, PassageList)
        self.assertEqual(fragment.english(), ["a"])


class HeadingTest(unittest.TestCase):
    def test_heading_anchor_carries_page_and_order(self):
        headings = _fragments({"type": "heading", "level": 1, "en": "A", "tr": "B"},
                              {"type": "heading", "level": 1, "en": "C", "tr": "D"})
        self.assertEqual([heading.anchor for heading in headings], ["h-12-1", "h-12-2"])

    def test_level_below_one_becomes_one(self):
        self.assertEqual(_only({"type": "heading", "level": 0, "en": "A", "tr": "B"}).level, 1)

    def test_level_above_three_becomes_three(self):
        self.assertEqual(_only({"type": "heading", "level": 4, "en": "A", "tr": "B"}).level, 3)

    def test_heading_is_turkish(self):
        self.assertIsInstance(_only({"type": "heading", "level": 2, "en": "A", "tr": "B"}), Heading)


class SilentBlockTest(unittest.TestCase):
    def test_chapter_block_is_written_by_the_chapter(self):
        self.assertEqual(_fragments({"type": "chapter", "num": 1, "en": "A", "tr": "B"}), [])

    def test_unknown_block_is_skipped(self):
        self.assertEqual(_fragments({"type": "yeni"}), [])

    def test_legacy_html_block_is_skipped(self):
        self.assertEqual(_fragments({"type": "html", "html": "<p/>"}), [])


class MediaBlockTest(unittest.TestCase):
    def test_image_points_into_the_page_folder(self):
        self.assertIn('src="../images/page-12/fig%201.png"', _only({"type": "image", "src": "fig 1.png"}).html)

    def test_display_math_is_its_png_with_text_as_alt(self):
        html = _only({"type": "math", "src": "eq-1.png", "text": "a < b"}).html
        self.assertIn('src="../images/page-12/eq-1.png" alt="a &lt; b"', html)

    def test_inline_equation_placeholder_becomes_png(self):
        passage = _only(_para(("x ⟦eq-2⟧ y", "x ⟦eq-2⟧ y")), math=[{"id": "eq-2", "src": "eq-2.png", "text": "z"}])
        self.assertIn('<img class="math-inline" src="../images/page-12/eq-2.png" alt="z"/>', passage.tr_html)

    def test_unknown_inline_placeholder_stays(self):
        self.assertEqual(_only(_para(("x ⟦eq-9⟧", "x ⟦eq-9⟧"))).tr_html, "x ⟦eq-9⟧")

    def test_image_href_is_relative_to_content_root(self):
        self.assertEqual(image_href(3, "a.png"), "images/page-3/a.png")


class TableAndCodeTest(unittest.TestCase):
    def test_header_rows_become_th(self):
        table = {"type": "table", "header_rows": 1,
                 "rows": [[{"en": "Name", "tr": "Ad"}], [{"en": "1", "tr": "1"}]]}
        self.assertEqual(_only(table).html, '<table class="book-table"><thead><tr><th>Ad</th></tr></thead>'
                                            '<tbody><tr><td>1</td></tr></tbody></table>')

    def test_table_without_header_has_no_thead(self):
        table = {"type": "table", "rows": [[{"en": "1", "tr": "1"}]]}
        self.assertNotIn("<thead>", _only(table).html)

    def test_code_caption_is_turkish_above_the_code(self):
        code = {"type": "code", "code": "x = 1", "caption": {"en": "Listing", "tr": "Liste"}}
        self.assertTrue(_only(code).html.startswith('<p class="caption">Liste</p><pre'))


if __name__ == "__main__":
    unittest.main()
