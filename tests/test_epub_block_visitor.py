import unittest

import _paths  # noqa: F401
from epub.block_visitor import EpubBlockVisitor, image_href
from epub.fragments import BodyParagraph, Heading
from page_document import PageDocument

PAGE = 12
FIRST_NOTE = 1


def _fragments(*blocks, math=()):
    return EpubBlockVisitor(PageDocument({"page": PAGE, "blocks": list(blocks), "math": list(math)})).fragments()


def _only(*blocks, math=()):
    [fragment] = _fragments(*blocks, math=math)
    return fragment


def _html(block):
    fragment = _only(block)
    return fragment.render(FIRST_NOTE)


def _para(*sentences, style=None):
    block = {"type": "para", "sentences": [{"en": en, "tr": tr} for en, tr in sentences]}
    return {**block, "style": style} if style else block


class TextBlockTest(unittest.TestCase):
    def test_para_joins_turkish_sentences(self):
        self.assertTrue(_html(_para(("One.", "Bir."), ("Two.", "İki."))).startswith('<p class="para">Bir. İki. <a'))

    def test_para_joins_english_sentences(self):
        passage = _only(_para(("One.", "Bir."), ("Two.", "İki.")))
        self.assertEqual(passage.english(), ["One. Two."])

    def test_para_is_a_body_paragraph(self):
        self.assertIsInstance(_only(_para(("One.", "Bir."))), BodyParagraph)

    def test_para_style_joins_its_class(self):
        self.assertTrue(_html(_para(("A.", "B."), style="quote")).startswith('<p class="para quote">'))

    def test_caption_class_is_its_block_type(self):
        self.assertTrue(_html({"type": "caption", "en": "Figure", "tr": "Şekil"}).startswith('<p class="caption">'))

    def test_caption_carries_its_english_note(self):
        caption = _only({"type": "caption", "en": "Figure", "tr": "Şekil"})
        self.assertEqual(caption.english(), ["Figure"])

    def test_ordered_list_is_numbered(self):
        self.assertTrue(_html({"type": "list", "ordered": True, "items": []}).startswith('<ol class="list">'))

    def test_list_items_carry_their_english_notes(self):
        fragment = _only({"type": "list", "items": [{"en": "a", "tr": "b"}]})
        self.assertEqual(fragment.english(), ["a"])


class HeadingTest(unittest.TestCase):
    def test_heading_anchor_carries_page_and_order(self):
        headings = _fragments({"type": "heading", "level": 1, "en": "A", "tr": "B"},
                              {"type": "heading", "level": 1, "en": "C", "tr": "D"})
        self.assertEqual([heading.render(FIRST_NOTE) for heading in headings],
                         [f'<h2 id="h-{PAGE}-1">B</h2>', f'<h2 id="h-{PAGE}-2">D</h2>'])

    def test_level_below_one_becomes_one(self):
        self.assertTrue(_html({"type": "heading", "level": 0, "en": "A", "tr": "B"}).startswith("<h2 "))

    def test_level_above_three_becomes_three(self):
        self.assertTrue(_html({"type": "heading", "level": 4, "en": "A", "tr": "B"}).startswith("<h4 "))

    def test_heading_is_turkish(self):
        self.assertIsInstance(_only({"type": "heading", "level": 2, "en": "A", "tr": "B"}), Heading)


class SilentBlockTest(unittest.TestCase):
    def test_chapter_block_is_written_by_the_chapter(self):
        self.assertEqual(_fragments({"type": "chapter", "num": 1, "en": "A", "tr": "B"}), [])

    def test_unknown_block_is_skipped(self):
        self.assertEqual(_fragments({"type": "yeni"}), [])


class MediaBlockTest(unittest.TestCase):
    def test_image_points_into_the_page_folder(self):
        self.assertIn(f'src="../images/page-{PAGE}/fig%201.png"', _html({"type": "image", "src": "fig 1.png"}))

    def test_display_math_is_its_png_with_text_as_alt(self):
        html = _html({"type": "math", "src": "eq-1.png", "text": "a < b"})
        self.assertIn(f'src="../images/page-{PAGE}/eq-1.png" alt="a &lt; b"', html)

    def test_inline_equation_placeholder_becomes_png(self):
        passage = _only(_para(("x ⟦eq-2⟧ y", "x ⟦eq-2⟧ y")), math=[{"id": "eq-2", "src": "eq-2.png", "text": "z"}])
        self.assertIn(f'<img class="math-inline" src="../images/page-{PAGE}/eq-2.png" alt="z"/>',
                      passage.render(FIRST_NOTE))

    def test_inline_equation_in_the_english_note_becomes_png(self):
        passage = _only(_para(("x ⟦eq-2⟧", "y ⟦eq-2⟧")), math=[{"id": "eq-2", "src": "eq-2.png", "text": "z"}])
        self.assertEqual(passage.english(),
                         [f'x <img class="math-inline" src="../images/page-{PAGE}/eq-2.png" alt="z"/>'])

    def test_unknown_inline_placeholder_stays(self):
        self.assertEqual(_html(_para(("x ⟦eq-9⟧", "x ⟦eq-9⟧"))), '<p class="para">x ⟦eq-9⟧</p>')

    def test_image_href_is_relative_to_content_root(self):
        self.assertEqual(image_href(3, "a.png"), "images/page-3/a.png")


class TableAndCodeTest(unittest.TestCase):
    def test_header_rows_become_th(self):
        table = {"type": "table", "header_rows": 1,
                 "rows": [[{"en": "Name", "tr": "Ad"}], [{"en": "1", "tr": "1"}]]}
        self.assertEqual(_html(table), '<table class="book-table"><thead><tr><th>Ad</th></tr></thead>'
                                          '<tbody><tr><td>1</td></tr></tbody></table>')

    def test_table_without_header_has_no_thead(self):
        table = {"type": "table", "rows": [[{"en": "1", "tr": "1"}]]}
        self.assertNotIn("<thead>", _html(table))

    def test_code_caption_is_turkish_above_the_code(self):
        code = {"type": "code", "code": "x = 1", "caption": {"en": "Listing", "tr": "Liste"}}
        self.assertTrue(_html(code).startswith('<p class="caption">Liste</p><pre'))


if __name__ == "__main__":
    unittest.main()
