import re
import unittest

import _paths  # noqa: F401
from epub.fragments import BodyParagraph, Fragment, Heading, Paragraph, Passage, PassageList, notes_section

MARK = "<span/>"
FIRST_NOTE = 1
LATER_NOTE = 7
QUOTE_STYLE = "para quote"


def _passage(en):
    return Passage("Tr.", en)


def _para(en, tr="Tr."):
    return BodyParagraph("para", Passage(tr, en))


class PassageOpenEndTest(unittest.TestCase):
    def test_sentence_without_ending_is_open(self):
        self.assertTrue(_passage("A well-known example of a masked language").is_open())

    def test_sentence_with_full_stop_is_closed(self):
        self.assertFalse(_passage("The model is BERT.").is_open())

    def test_closing_quote_ends_a_sentence(self):
        self.assertFalse(_passage("He said “stop.”").is_open())

    def test_closing_parenthesis_ends_a_sentence(self):
        self.assertFalse(_passage("See the paper (Devlin et al., 2018)").is_open())

    def test_footnote_mark_after_full_stop_does_not_open_it(self):
        self.assertFalse(_passage("The model is BERT.<sup>3</sup>").is_open())

    def test_trailing_space_is_ignored(self):
        self.assertFalse(_passage("Done.  ").is_open())

    def test_empty_paragraph_is_not_open(self):
        self.assertFalse(_passage("").is_open())


class BodyParagraphJoinTest(unittest.TestCase):
    def test_open_paragraph_continues_into_next_paragraph(self):
        self.assertTrue(_para("of a masked").continues_into(_para("model is BERT.")))

    def test_closed_paragraph_does_not_continue(self):
        self.assertFalse(_para("Done.").continues_into(_para("next")))

    def test_different_styles_do_not_continue(self):
        self.assertFalse(_para("of a").continues_into(BodyParagraph(QUOTE_STYLE, _passage("quote."))))

    def test_only_a_body_paragraph_continues(self):
        self.assertFalse(_para("of a").continues_into(Paragraph("para", Passage("Şekil", "Figure"))))

    def test_join_keeps_the_english_of_both(self):
        joined = _para("of a masked", "Maskeli bir").join(_para("model.", "model."), MARK)
        self.assertEqual(joined.english(), ["of a masked model."])

    def test_join_marks_the_page_inside_the_turkish(self):
        joined = _para("of a masked", "Maskeli bir").join(_para("model.", "model."), MARK)
        self.assertTrue(joined.render(FIRST_NOTE).startswith(f'<p class="para">Maskeli bir {MARK}model. <a'))

    def test_join_drops_continuation_mark(self):
        joined = _para("of a", "Bir").join(_para("model. Next.", "… Sonraki."), MARK)
        self.assertTrue(joined.render(FIRST_NOTE).startswith(f'<p class="para">Bir {MARK}Sonraki. <a'))


class PassageNoteTest(unittest.TestCase):
    def test_translated_passage_links_its_note(self):
        html = Paragraph("caption", Passage("Şekil", "Figure")).render(LATER_NOTE)
        self.assertEqual(html, f'<p class="caption">Şekil <a epub:type="noteref" id="ref-{LATER_NOTE}" '
                               f'href="#note-{LATER_NOTE}" class="en-ref">EN</a></p>')

    def test_untranslated_passage_has_no_note(self):
        self.assertEqual(Passage("Figure", "Figure").english(), [])

    def test_passage_without_english_has_no_note(self):
        self.assertEqual(Passage("Şekil", "").english(), [])


class PassageListTest(unittest.TestCase):
    def test_items_are_numbered_from_first_note_skipping_untranslated(self):
        items = [Passage("Bir", "One"), Passage("Two", "Two"), Passage("Üç", "Three")]
        html = PassageList("ul", items).render(LATER_NOTE)
        numbers = [int(number) for number in re.findall(r'href="#note-(\d+)"', html)]
        self.assertEqual(numbers, [LATER_NOTE, LATER_NOTE + 1])

    def test_english_lists_each_item(self):
        items = [Passage("Bir", "One"), Passage("İki", "Two")]
        self.assertEqual(PassageList("ol", items).english(), ["One", "Two"])

    def test_ordered_list_uses_ol(self):
        self.assertTrue(PassageList("ol", []).render(FIRST_NOTE).startswith('<ol class="list">'))


class HeadingTest(unittest.TestCase):
    def test_first_level_heading_is_a_toc_entry(self):
        self.assertEqual(Heading(1, "<em>Giriş</em>", "h-3-1").toc_entries(), [("Giriş", "h-3-1")])

    def test_lower_heading_is_not_a_toc_entry(self):
        self.assertEqual(Heading(2, "Alt", "h-3-2").toc_entries(), [])

    def test_level_one_heading_is_h2_under_the_chapter_title(self):
        self.assertEqual(Heading(1, "Giriş", "h-3-1").render(1), '<h2 id="h-3-1">Giriş</h2>')


class NotesSectionTest(unittest.TestCase):
    def test_no_notes_no_section(self):
        self.assertEqual(notes_section([]), "")

    def test_notes_are_numbered_from_one_in_english(self):
        section = notes_section(["One", "Two"])
        self.assertIn('id="note-2" lang="en"', section)
        self.assertIn('href="#ref-1"', section)

    def test_plain_fragment_has_no_notes(self):
        self.assertEqual(Fragment("<hr/>").english(), [])


if __name__ == "__main__":
    unittest.main()
