import re
import unittest
from xml.etree import ElementTree

import _paths  # noqa: F401
from epub.chapter import Chapter, ChapterFlow, page_mark
from epub.fragments import Fragment, ParaPassage
from page_document import PageDocument

CHAPTER = {"num": 2, "en": "Evaluation", "tr": "Değerlendirme"}
PAGE = 5
RETURN_LINK = re.compile(r'class="card-page"><a href="#([^"]+)"')
NEXT_PAGE = 6
PAGE_END = "<p>ek</p>"
CLOSED_PAGE = [ParaPassage("para", "Bitti.", "Done.")]
OPEN_PAGE = [ParaPassage("para", "Bir", "of a")]
NEXT_PAGE_PARAS = [ParaPassage("para", "Sonraki.", "Next.")]
CONTINUATION = [ParaPassage("para", "model.", "model."), ParaPassage("para", "Sonraki.", "Next.")]
CARD = {"kind": "explain", "title": {"en": "A", "tr": "B"}, "summary": {"en": "S", "tr": "Ö"}}


def _para(en, tr):
    return ParaPassage("para", tr, en)


def _page(number, blocks):
    return PageDocument({"page": number, "chapter": CHAPTER, "blocks": blocks})


def _page_with_cards(number, cards):
    return PageDocument({"page": number, "chapter": CHAPTER, "blocks": [_para_block("A.", "B.")], "concepts": cards})


def _flow_ending_with_page_end(first_page):
    flow = ChapterFlow()
    flow.add_page(PAGE, first_page)
    flow.end_page([Fragment(PAGE_END)])
    return flow


def _flow_across_page_end(first_page, next_page):
    flow = _flow_ending_with_page_end(first_page)
    flow.add_page(NEXT_PAGE, next_page)
    return flow


def _return_target(xhtml):
    """Karttaki "s. N" bağlantısının hedefi."""
    return re.findall(RETURN_LINK, xhtml)[0]


def _para_block(en, tr):
    return {"type": "para", "sentences": [{"en": en, "tr": tr}]}


class ChapterFlowTest(unittest.TestCase):
    def test_new_page_starts_with_its_page_mark(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("Done.", "Bitti.")])
        self.assertTrue(flow.render().startswith(page_mark(PAGE)))

    def test_open_paragraph_absorbs_next_page_continuation(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("of a masked", "Maskeli bir")])
        flow.add_page(NEXT_PAGE, [_para("model.", "modeli."), _para("Next.", "Sonraki.")])
        self.assertEqual(flow.english(), ["of a masked model.", "Next."])

    def test_page_mark_sits_inside_the_joined_paragraph(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("of a", "Bir")])
        flow.add_page(NEXT_PAGE, [_para("model.", "model.")])
        self.assertIn(f"Bir {page_mark(NEXT_PAGE)}model.", flow.render())

    def test_closed_paragraph_keeps_next_page_apart(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("Done.", "Bitti.")])
        flow.add_page(NEXT_PAGE, [_para("Next.", "Sonraki.")])
        self.assertIn(f"</p>\n{page_mark(NEXT_PAGE)}\n<p", flow.render())

    def test_empty_page_still_leaves_its_mark(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [])
        self.assertEqual(flow.render(), page_mark(PAGE))

    def test_notes_are_numbered_through_the_chapter(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("One.", "Bir."), Fragment("<hr/>"), _para("Two.", "İki.")])
        self.assertIn('href="#note-2"', flow.render().split("<hr/>")[1])


class PageEndTest(unittest.TestCase):
    """Sayfa sonu eki (kart satırı) bölünen paragrafı kırmaz; birleşik paragrafın arkasına düşer."""

    def test_page_end_follows_the_page(self):
        html = _flow_across_page_end(CLOSED_PAGE, NEXT_PAGE_PARAS).render()
        self.assertLess(html.index(PAGE_END), html.index(page_mark(NEXT_PAGE)))

    def test_open_paragraph_still_joins_across_a_page_end(self):
        self.assertIn("of a model.", _flow_across_page_end(OPEN_PAGE, CONTINUATION).english())

    def test_page_end_sits_after_the_joined_paragraph(self):
        html = _flow_across_page_end(OPEN_PAGE, CONTINUATION).render()
        positions = [html.index("model."), html.index(PAGE_END), html.index("Sonraki.")]
        self.assertEqual(positions, sorted(positions))

    def test_last_page_end_closes_the_chapter(self):
        self.assertTrue(_flow_ending_with_page_end(CLOSED_PAGE).render().endswith(PAGE_END))

    def test_page_end_is_used_once(self):
        self.assertEqual(_flow_across_page_end(CLOSED_PAGE, NEXT_PAGE_PARAS).render().count(PAGE_END), 1)


class ChapterTest(unittest.TestCase):
    def setUp(self):
        self.chapter = Chapter("chapter-02.xhtml", CHAPTER)

    def test_chapter_records_its_pages(self):
        self.chapter.add(_page(PAGE, [_para_block("A.", "B.")]))
        self.chapter.add(_page(NEXT_PAGE, [_para_block("C.", "D.")]))
        self.assertEqual(self.chapter.page_links(), [(PAGE, f"chapter-02.xhtml#page-{PAGE}"), (NEXT_PAGE, f"chapter-02.xhtml#page-{NEXT_PAGE}")])

    def test_title_is_turkish(self):
        self.assertEqual(self.chapter.title(), "Değerlendirme")

    def test_untranslated_title_falls_back_to_english(self):
        self.assertEqual(Chapter("c.xhtml", {"num": 1, "en": "Intro", "tr": ""}).title(), "Intro")

    def test_cards_add_a_toc_entry(self):
        card = {"kind": "explain", "title": {"en": "A", "tr": "B"}, "summary": {"en": "S", "tr": "Ö"}}
        self.chapter.add(_page_with_cards(PAGE, [card]))
        self.assertEqual(self.chapter.toc_entries()[-1][0], "Kavram kartları")

    def test_card_without_summary_is_left_out_of_the_chapter(self):
        empty = {"kind": "explain", "title": {"en": "A", "tr": "B"}}
        self.chapter.add(_page_with_cards(PAGE, [empty]))
        self.assertNotIn('<section class="cards">', self.chapter.xhtml())

    def test_page_with_cards_ends_with_its_card_line(self):
        self.chapter.add(_page_with_cards(PAGE, [CARD]))
        self.chapter.add(_page(NEXT_PAGE, [_para_block("C.", "D.")]))
        xhtml = self.chapter.xhtml()
        self.assertLess(xhtml.index('class="card-links"'), xhtml.index(page_mark(NEXT_PAGE)))

    def test_card_return_link_lands_on_its_card_line(self):
        self.chapter.add(_page_with_cards(PAGE, [CARD]))
        xhtml = self.chapter.xhtml()
        self.assertIn(f'<p class="card-links" id="{_return_target(xhtml)}">', xhtml)

    def test_page_without_cards_has_no_card_line(self):
        self.chapter.add(_page(PAGE, [_para_block("A.", "B.")]))
        self.assertNotIn('class="card-links"', self.chapter.xhtml())

    def test_card_without_summary_gets_no_card_line(self):
        self.chapter.add(_page_with_cards(PAGE, [{"kind": "explain", "title": {"en": "A", "tr": "B"}}]))
        self.assertNotIn('class="card-links"', self.chapter.xhtml())

    def test_chapter_without_cards_has_no_cards_entry(self):
        self.chapter.add(_page(PAGE, [_para_block("A.", "B.")]))
        self.assertEqual(self.chapter.toc_entries(), [])

    def test_xhtml_is_well_formed_and_holds_heading_text_and_notes(self):
        self.chapter.add(_page(PAGE, [_para_block("A & B.", "A ve B.")]))
        xhtml = self.chapter.xhtml()
        ElementTree.fromstring(xhtml.encode("utf-8"))
        self.assertLess(xhtml.index("Bölüm 2"), xhtml.index("A ve B."))
        self.assertLess(xhtml.index("A ve B."), xhtml.index('id="note-1"'))

    def test_unnumbered_chapter_has_no_number_label(self):
        chapter = Chapter("c.xhtml", {"num": 0, "en": "Preface", "tr": "Önsöz"})
        self.assertNotIn("Bölüm", chapter.xhtml())


if __name__ == "__main__":
    unittest.main()
