import unittest
from xml.etree import ElementTree

import _paths  # noqa: F401
from epub.chapter import Chapter, ChapterFlow, page_mark
from epub.fragments import Fragment, ParaPassage
from page_document import PageDocument

CHAPTER = {"num": 2, "en": "Evaluation", "tr": "Değerlendirme"}
PAGE = 5
NEXT_PAGE = 6
PAGE_END = "<p>ek</p>"
CLOSED_PAGE = [ParaPassage("para", "Bitti.", "Done.")]
OPEN_PAGE = [ParaPassage("para", "Bir", "of a")]
NEXT_PAGE_PARAS = [ParaPassage("para", "Sonraki.", "Next.")]
CONTINUATION = [ParaPassage("para", "model.", "model."), ParaPassage("para", "Sonraki.", "Next.")]
CARD = {"kind": "explain", "title": {"en": "A", "tr": "B"}, "summary": {"en": "S", "tr": "Ö"}}


def _para(en, tr):
    return ParaPassage("para", tr, en)


def _page(number, blocks, concepts=()):
    return PageDocument({"page": number, "chapter": CHAPTER, "blocks": blocks, "concepts": list(concepts)})


def _flow_ending_with_page_end(first_page):
    flow = ChapterFlow()
    flow.add_page(PAGE, first_page)
    flow.end_page([Fragment(PAGE_END)])
    return flow


def _flow_across_page_end(first_page, next_page):
    flow = _flow_ending_with_page_end(first_page)
    flow.add_page(NEXT_PAGE, next_page)
    return flow


def _para_block(en, tr):
    return {"type": "para", "sentences": [{"en": en, "tr": tr}]}


class ChapterFlowTest(unittest.TestCase):
    def test_new_page_starts_with_its_page_mark(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("Done.", "Bitti.")])
        self.assertEqual(flow.fragments[0].html, page_mark(PAGE))

    def test_open_paragraph_absorbs_next_page_continuation(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("of a masked", "Maskeli bir")])
        flow.add_page(NEXT_PAGE, [_para("model.", "model."), _para("Next.", "Sonraki.")])
        self.assertEqual([fragment.en_html for fragment in flow.fragments[1:]], ["of a masked model.", "Next."])

    def test_page_mark_sits_inside_the_joined_paragraph(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("of a", "Bir")])
        flow.add_page(NEXT_PAGE, [_para("model.", "model.")])
        self.assertIn(page_mark(NEXT_PAGE), flow.fragments[-1].tr_html)

    def test_closed_paragraph_keeps_next_page_apart(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [_para("Done.", "Bitti.")])
        flow.add_page(NEXT_PAGE, [_para("Next.", "Sonraki.")])
        self.assertEqual(flow.fragments[2].html, page_mark(NEXT_PAGE))

    def test_empty_page_still_leaves_its_mark(self):
        flow = ChapterFlow()
        flow.add_page(PAGE, [])
        self.assertEqual(len(flow.fragments), 1)

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
        self.assertEqual(self.chapter.pages, [PAGE, NEXT_PAGE])

    def test_title_is_turkish(self):
        self.assertEqual(self.chapter.title(), "Değerlendirme")

    def test_untranslated_title_falls_back_to_english(self):
        self.assertEqual(Chapter("c.xhtml", {"num": 1, "en": "Intro", "tr": ""}).title(), "Intro")

    def test_cards_add_a_toc_entry(self):
        card = {"kind": "explain", "title": {"en": "A", "tr": "B"}, "summary": {"en": "S", "tr": "Ö"}}
        self.chapter.add(_page(PAGE, [], concepts=[card]))
        self.assertEqual(self.chapter.toc_entries()[-1][0], "Kavram kartları")

    def test_card_without_summary_is_left_out_of_the_chapter(self):
        empty = {"kind": "explain", "title": {"en": "A", "tr": "B"}}
        self.chapter.add(_page(PAGE, [_para_block("A.", "B.")], concepts=[empty]))
        self.assertEqual((self.chapter.page_cards, self.chapter.toc_entries()), ([], []))

    def test_page_with_cards_ends_with_its_card_line(self):
        self.chapter.add(_page(PAGE, [_para_block("A.", "B.")], concepts=[CARD]))
        self.chapter.add(_page(NEXT_PAGE, [_para_block("C.", "D.")]))
        xhtml = self.chapter.xhtml()
        self.assertLess(xhtml.index('class="card-links"'), xhtml.index(page_mark(NEXT_PAGE)))

    def test_page_without_cards_has_no_card_line(self):
        self.chapter.add(_page(PAGE, [_para_block("A.", "B.")]))
        self.assertNotIn('class="card-links"', self.chapter.xhtml())

    def test_card_without_summary_gets_no_card_line(self):
        self.chapter.add(_page(PAGE, [_para_block("A.", "B.")], concepts=[{"kind": "explain", "title": {"en": "A", "tr": "B"}}]))
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
