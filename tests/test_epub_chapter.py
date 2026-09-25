import unittest
from xml.etree import ElementTree

import _paths  # noqa: F401
from epub.chapter import Chapter, ChapterFlow, page_mark
from epub.fragments import Fragment, ParaPassage
from page_document import PageDocument

CHAPTER = {"num": 2, "en": "Evaluation", "tr": "Değerlendirme"}


def _para(en, tr):
    return ParaPassage("para", tr, en)


def _page(number, blocks, concepts=()):
    return PageDocument({"page": number, "chapter": CHAPTER, "blocks": blocks, "concepts": list(concepts)})


def _para_block(en, tr):
    return {"type": "para", "sentences": [{"en": en, "tr": tr}]}


class ChapterFlowTest(unittest.TestCase):
    def test_new_page_starts_with_its_page_mark(self):
        flow = ChapterFlow()
        flow.add_page(5, [_para("Done.", "Bitti.")])
        self.assertEqual(flow.fragments[0].html, page_mark(5))

    def test_open_paragraph_absorbs_next_page_continuation(self):
        flow = ChapterFlow()
        flow.add_page(5, [_para("of a masked", "Maskeli bir")])
        flow.add_page(6, [_para("model.", "model."), _para("Next.", "Sonraki.")])
        self.assertEqual([fragment.en_html for fragment in flow.fragments[1:]], ["of a masked model.", "Next."])

    def test_page_mark_sits_inside_the_joined_paragraph(self):
        flow = ChapterFlow()
        flow.add_page(5, [_para("of a", "Bir")])
        flow.add_page(6, [_para("model.", "model.")])
        self.assertIn(page_mark(6), flow.fragments[-1].tr_html)

    def test_closed_paragraph_keeps_next_page_apart(self):
        flow = ChapterFlow()
        flow.add_page(5, [_para("Done.", "Bitti.")])
        flow.add_page(6, [_para("Next.", "Sonraki.")])
        self.assertEqual(flow.fragments[2].html, page_mark(6))

    def test_empty_page_still_leaves_its_mark(self):
        flow = ChapterFlow()
        flow.add_page(5, [])
        self.assertEqual(len(flow.fragments), 1)

    def test_notes_are_numbered_through_the_chapter(self):
        flow = ChapterFlow()
        flow.add_page(5, [_para("One.", "Bir."), Fragment("<hr/>"), _para("Two.", "İki.")])
        self.assertIn('href="#note-2"', flow.render().split("<hr/>")[1])


class ChapterTest(unittest.TestCase):
    def setUp(self):
        self.chapter = Chapter("chapter-02.xhtml", CHAPTER)

    def test_chapter_records_its_pages(self):
        self.chapter.add(_page(5, [_para_block("A.", "B.")]))
        self.chapter.add(_page(6, [_para_block("C.", "D.")]))
        self.assertEqual(self.chapter.pages, [5, 6])

    def test_title_is_turkish(self):
        self.assertEqual(self.chapter.title(), "Değerlendirme")

    def test_untranslated_title_falls_back_to_english(self):
        self.assertEqual(Chapter("c.xhtml", {"num": 1, "en": "Intro", "tr": ""}).title(), "Intro")

    def test_cards_add_a_toc_entry(self):
        card = {"kind": "explain", "title": {"en": "A", "tr": "B"}, "summary": {"en": "S", "tr": "Ö"}}
        self.chapter.add(_page(5, [], concepts=[card]))
        self.assertEqual(self.chapter.toc_entries()[-1][0], "Kavram kartları")

    def test_card_without_summary_is_left_out_of_the_chapter(self):
        empty = {"kind": "explain", "title": {"en": "A", "tr": "B"}}
        self.chapter.add(_page(5, [_para_block("A.", "B.")], concepts=[empty]))
        self.assertEqual((self.chapter.page_cards, self.chapter.toc_entries()), ([], []))

    def test_chapter_without_cards_has_no_cards_entry(self):
        self.chapter.add(_page(5, [_para_block("A.", "B.")]))
        self.assertEqual(self.chapter.toc_entries(), [])

    def test_xhtml_is_well_formed_and_holds_heading_text_and_notes(self):
        self.chapter.add(_page(5, [_para_block("A & B.", "A ve B.")]))
        xhtml = self.chapter.xhtml()
        ElementTree.fromstring(xhtml.encode("utf-8"))
        self.assertLess(xhtml.index("Bölüm 2"), xhtml.index("A ve B."))
        self.assertLess(xhtml.index("A ve B."), xhtml.index('id="note-1"'))

    def test_unnumbered_chapter_has_no_number_label(self):
        chapter = Chapter("c.xhtml", {"num": 0, "en": "Preface", "tr": "Önsöz"})
        self.assertNotIn("Bölüm", chapter.xhtml())


if __name__ == "__main__":
    unittest.main()
