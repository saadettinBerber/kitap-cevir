import unittest

import _paths  # noqa: F401
from epub.block_visitor import EpubBlockVisitor, image_href
from epub.fragments import BodyParagraph, Heading
from page_document import PageDocument

PAGE = 12
FIRST_NOTE = 1
EQUATION = {"id": "eq-2", "src": "eq-2.png", "text": "z"}


class Visited:
    """Ziyaretçinin bloklardan kurduğu parçalar; testler tek parçanın HTML'ini ya da İngilizce notunu sorar."""

    def __init__(self, *blocks, math=()):
        page = PageDocument({"page": PAGE, "blocks": list(blocks), "math": list(math)})
        self._fragments = EpubBlockVisitor(page).fragments()

    def fragments(self):
        return list(self._fragments)

    def only(self):
        [fragment] = self._fragments
        return fragment

    def html(self):
        [fragment] = self._fragments
        return fragment.render(FIRST_NOTE)

    def english(self):
        [fragment] = self._fragments
        return fragment.english()


def _para(*sentences, style=None):
    block = {"type": "para", "sentences": [{"en": en, "tr": tr} for en, tr in sentences]}
    return {**block, "style": style} if style else block


class TextBlockTest(unittest.TestCase):
    def test_para_joins_turkish_sentences(self):
        html = Visited(_para(("One.", "Bir."), ("Two.", "İki."))).html()
        self.assertTrue(html.startswith('<p class="para">Bir. İki. <a'))

    def test_para_joins_english_sentences(self):
        self.assertEqual(Visited(_para(("One.", "Bir."), ("Two.", "İki."))).english(), ["One. Two."])

    def test_para_is_a_body_paragraph(self):
        self.assertIsInstance(Visited(_para(("One.", "Bir."))).only(), BodyParagraph)

    def test_para_style_joins_its_class(self):
        self.assertTrue(Visited(_para(("A.", "B."), style="quote")).html().startswith('<p class="para quote">'))

    def test_caption_class_is_its_block_type(self):
        html = Visited({"type": "caption", "en": "Figure", "tr": "Şekil"}).html()
        self.assertTrue(html.startswith('<p class="caption">'))

    def test_footnote_class_is_its_block_type(self):
        html = Visited({"type": "footnote", "en": "Note", "tr": "Not"}).html()
        self.assertTrue(html.startswith('<p class="footnote">'))

    def test_caption_carries_its_english_note(self):
        self.assertEqual(Visited({"type": "caption", "en": "Figure", "tr": "Şekil"}).english(), ["Figure"])

    def test_ordered_list_is_numbered(self):
        self.assertTrue(Visited({"type": "list", "ordered": True, "items": []}).html().startswith('<ol class="list">'))

    def test_unordered_list_is_bulleted(self):
        self.assertTrue(Visited({"type": "list", "items": []}).html().startswith('<ul class="list">'))

    def test_list_items_carry_their_english_notes(self):
        self.assertEqual(Visited({"type": "list", "items": [{"en": "a", "tr": "b"}]}).english(), ["a"])

    def test_every_list_item_is_written(self):
        items = [{"en": "a", "tr": "b"}, {"en": "c", "tr": "d"}]
        self.assertEqual(Visited({"type": "list", "items": items}).english(), ["a", "c"])


class HeadingTest(unittest.TestCase):
    def test_heading_anchor_carries_page_and_order(self):
        headings = Visited({"type": "heading", "level": 1, "en": "A", "tr": "B"},
                              {"type": "heading", "level": 1, "en": "C", "tr": "D"}).fragments()
        self.assertEqual([heading.render(FIRST_NOTE) for heading in headings],
                         [f'<h2 id="h-{PAGE}-1">B</h2>', f'<h2 id="h-{PAGE}-2">D</h2>'])

    def test_level_below_one_becomes_one(self):
        self.assertTrue(Visited({"type": "heading", "level": 0, "en": "A", "tr": "B"}).html().startswith("<h2 "))

    def test_level_above_three_becomes_three(self):
        self.assertTrue(Visited({"type": "heading", "level": 4, "en": "A", "tr": "B"}).html().startswith("<h4 "))

    def test_heading_is_turkish(self):
        self.assertIsInstance(Visited({"type": "heading", "level": 2, "en": "A", "tr": "B"}).only(), Heading)


class SilentBlockTest(unittest.TestCase):
    def test_chapter_block_is_written_by_the_chapter(self):
        self.assertEqual(Visited({"type": "chapter", "num": 1, "en": "A", "tr": "B"}).fragments(), [])

    def test_unknown_block_is_skipped(self):
        self.assertEqual(Visited({"type": "yeni"}).fragments(), [])


class MediaBlockTest(unittest.TestCase):
    def test_image_points_into_the_page_folder(self):
        self.assertIn(f'src="../images/page-{PAGE}/fig%201.png"', Visited({"type": "image", "src": "fig 1.png"}).html())

    def test_display_math_is_its_png_with_text_as_alt(self):
        html = Visited({"type": "math", "src": "eq-1.png", "text": "a < b"}).html()
        self.assertIn(f'src="../images/page-{PAGE}/eq-1.png" alt="a &lt; b"', html)

    def test_inline_equation_placeholder_becomes_png(self):
        html = Visited(_para(("x ⟦eq-2⟧ y", "x ⟦eq-2⟧ y")), math=[EQUATION]).html()
        self.assertIn(f'<img class="math-inline" src="../images/page-{PAGE}/eq-2.png" alt="z"/>', html)

    def test_inline_equation_in_the_english_note_becomes_png(self):
        self.assertEqual(Visited(_para(("x ⟦eq-2⟧", "y ⟦eq-2⟧")), math=[EQUATION]).english(),
                         [f'x <img class="math-inline" src="../images/page-{PAGE}/eq-2.png" alt="z"/>'])

    def test_unknown_inline_placeholder_stays(self):
        self.assertEqual(Visited(_para(("x ⟦eq-9⟧", "x ⟦eq-9⟧"))).html(), '<p class="para">x ⟦eq-9⟧</p>')

    def test_image_href_is_relative_to_content_root(self):
        self.assertEqual(image_href(3, "a.png"), "images/page-3/a.png")


class TableAndCodeTest(unittest.TestCase):
    def test_header_rows_become_th(self):
        table = {"type": "table", "header_rows": 1,
                 "rows": [[{"en": "Name", "tr": "Ad"}], [{"en": "1", "tr": "1"}]]}
        self.assertEqual(Visited(table).html(), '<table class="book-table"><thead><tr><th>Ad</th></tr></thead>'
                                          '<tbody><tr><td>1</td></tr></tbody></table>')

    def test_table_without_header_has_no_thead(self):
        table = {"type": "table", "rows": [[{"en": "1", "tr": "1"}]]}
        self.assertNotIn("<thead>", Visited(table).html())

    def test_code_is_written_in_its_block(self):
        self.assertIn("x = 1", Visited({"type": "code", "code": "x = 1"}).html())

    def test_code_caption_is_turkish_above_the_code(self):
        code = {"type": "code", "code": "x = 1", "caption": {"en": "Listing", "tr": "Liste"}}
        self.assertTrue(Visited(code).html().startswith('<p class="caption">Liste</p><pre'))


if __name__ == "__main__":
    unittest.main()
