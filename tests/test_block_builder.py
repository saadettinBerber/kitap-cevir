"""BlockBuilder kuralları: düzen öğesinin türü, puntosu, fontu ve metni hangi
bloğu verir. Eşikler varsayılan ayarlardandır; iki yanı ayrı testte sınanır."""
import unittest

from pdf_fakes import element
from extraction.block_builder import (MAX_HEADING_CHARS, MINOR_HEADING_LEVEL, SECTION_LEVEL, SUBSECTION_LEVEL,
                                      BlockBuilder)
from extraction.settings import DEFAULT_EXTRACTION, with_defaults

BOX = (70, 280, 430, 300)
BODY_SIZE = 10.5
CODE = "getUser"
CHAPTER_NUMBER = DEFAULT_EXTRACTION["chapter_number_min_size"]
CHAPTER_TITLE = DEFAULT_EXTRACTION["chapter_title_min_size"]
SECTION = DEFAULT_EXTRACTION["section_min_size"]
SUBSECTION = DEFAULT_EXTRACTION["subsection_min_size"]
FOOTNOTE = DEFAULT_EXTRACTION["footnote_max_size"]
STEP = 0.1
CHAPTER = 7


class InlineCodeFixer:
    """TextFixer gibi: plain metni olduğu gibi bırakır, rich satır içi kodu işaretler."""

    def plain(self, text):
        return text or ""

    def rich(self, text):
        return text.replace(CODE, f"`{CODE}`")


def _blocks(text, **fields):
    """fields: düzen öğesinin alanları; verilmeyenler gövde puntosundaki bir paragrafınkidir."""
    builder = BlockBuilder(with_defaults({}), InlineCodeFixer())
    return builder.blocks_of(element(text, BOX, **{"kind": "paragraph", "font_size": BODY_SIZE, **fields}))


def _heading(text, size):
    return _blocks(text, kind="heading", font_size=size)


class HeadingSizeTest(unittest.TestCase):
    def test_digits_at_chapter_number_size_are_the_chapter_number(self):
        self.assertEqual(_heading(str(CHAPTER), CHAPTER_NUMBER), [{"type": "chapter_number", "num": CHAPTER}])

    def test_digits_just_below_chapter_number_size_are_a_chapter_title(self):
        self.assertEqual(_heading("7", CHAPTER_NUMBER - STEP), [{"type": "chapter", "en": "7"}])

    def test_words_at_chapter_number_size_are_a_chapter_title(self):
        self.assertEqual(_heading("Modularity", CHAPTER_NUMBER), [{"type": "chapter", "en": "Modularity"}])

    def test_text_at_chapter_title_size_is_the_chapter(self):
        self.assertEqual(_heading("Modularity", CHAPTER_TITLE), [{"type": "chapter", "en": "Modularity"}])

    def test_text_just_below_chapter_title_size_is_a_section(self):
        self.assertEqual(_heading("Modularity", CHAPTER_TITLE - STEP),
                         [{"type": "heading", "level": SECTION_LEVEL, "en": "Modularity"}])

    def test_section_size_is_level_one(self):
        self.assertEqual(_heading("Cohesion", SECTION)[0]["level"], SECTION_LEVEL)

    def test_just_below_section_size_is_level_two(self):
        self.assertEqual(_heading("Cohesion", SECTION - STEP)[0]["level"], SUBSECTION_LEVEL)

    def test_subsection_size_is_level_two(self):
        self.assertEqual(_heading("Cohesion", SUBSECTION)[0]["level"], SUBSECTION_LEVEL)

    def test_just_below_subsection_size_is_level_three(self):
        self.assertEqual(_heading("Cohesion", SUBSECTION - STEP)[0]["level"], MINOR_HEADING_LEVEL)


class HeadingTextTest(unittest.TestCase):
    def test_heading_text_is_plain(self):
        self.assertEqual(_heading(f"Using {CODE}", SECTION)[0]["en"], f"Using {CODE}")

    def test_listing_caption_in_heading_font_is_a_listing_caption(self):
        self.assertEqual(_heading("Listing 3-1. Hello", SECTION),
                         [{"type": "caption", "kind": "listing", "en": "Listing 3-1. Hello"}])

    def test_heading_ending_with_punctuation_is_a_paragraph(self):
        self.assertEqual(_heading("Modules matter:", SECTION)[0]["type"], "para")

    def test_heading_of_the_longest_length_stays_a_heading(self):
        self.assertEqual(_heading("x" * MAX_HEADING_CHARS, SECTION)[0]["type"], "heading")

    def test_longer_heading_is_a_paragraph(self):
        self.assertEqual(_heading("x" * (MAX_HEADING_CHARS + 1), SECTION)[0]["type"], "para")

    def test_empty_heading_gives_nothing(self):
        self.assertEqual(_heading("", SECTION), [])


class ParagraphTest(unittest.TestCase):
    def test_sentences_are_rich(self):
        self.assertEqual(_blocks(f"Call {CODE}. Then stop."),
                         [{"type": "para", "sentences": [{"en": f"Call `{CODE}`."}, {"en": "Then stop."}]}])

    def test_number_alone_gives_nothing(self):
        self.assertEqual(_blocks("42"), [])

    def test_table_caption(self):
        self.assertEqual(_blocks(f"Table 2-1. {CODE} costs"),
                         [{"type": "caption", "kind": "table", "en": f"Table 2-1. `{CODE}` costs"}])

    def test_equation_caption(self):
        self.assertEqual(_blocks("Equation 3-3. Abstractness"),
                         [{"type": "caption", "kind": "equation", "en": "Equation 3-3. Abstractness"}])

    def test_footnote_size_is_a_footnote(self):
        self.assertEqual(_blocks(f"1 See {CODE}.", font_size=FOOTNOTE),
                         [{"type": "footnote", "en": f"1 See `{CODE}`."}])

    def test_just_above_footnote_size_is_a_paragraph(self):
        self.assertEqual(_blocks("1 See the notes.", font_size=FOOTNOTE + STEP)[0]["type"], "para")

    def test_bold_heading_font_is_a_minor_heading(self):
        self.assertEqual(_blocks(f"About {CODE}", font="Arial-BoldMT"),
                         [{"type": "heading", "level": MINOR_HEADING_LEVEL, "en": f"About {CODE}"}])

    def test_regular_weight_of_the_bold_heading_font_is_a_paragraph(self):
        self.assertEqual(_blocks("About modules", font="ArialMT")[0]["type"], "para")

    def test_other_bold_font_is_a_paragraph(self):
        self.assertEqual(_blocks("About modules", font="Helvetica-Bold")[0]["type"], "para")

    def test_bibliography_entry_is_a_reference(self):
        self.assertEqual(_blocks("[Fowler]: Refactoring.")[0]["style"], "reference")

    def test_italic_bibliography_entry_is_still_a_reference(self):
        self.assertEqual(_blocks("[Fowler]: Refactoring.", font="Minion-Italic")[0]["style"], "reference")

    def test_italic_paragraph_is_a_quote(self):
        self.assertEqual(_blocks("Less is more.", font="Minion-Italic")[0]["style"], "quote")

    def test_plain_paragraph_has_no_style(self):
        self.assertNotIn("style", _blocks("Less is more.")[0])


class ListTest(unittest.TestCase):
    def test_numbered_list_item_keeps_its_number(self):
        self.assertEqual(_blocks("2. If the shop offers more.", kind="list item")[0]["sentences"][0]["en"],
                         "2. If the shop offers more.")

    def test_list_item_in_chapter_title_size_stays_a_list_item(self):
        [block] = _blocks("2. Big item", kind="list item", font_size=CHAPTER_TITLE)
        self.assertEqual(block["sentences"], [{"en": "2. Big item"}])

    def test_list_items_are_rich_without_markers(self):
        items = (element(f"1. Call {CODE}", BOX, "list item"), element("2. Stop", BOX, "list item"))
        self.assertEqual(_blocks("", kind="list", list_items=items, is_ordered=True),
                         [{"type": "list", "ordered": True, "items": [{"en": f"Call `{CODE}`"}, {"en": "Stop"}]}])


class OtherKindsTest(unittest.TestCase):
    def test_table_cells_are_rich(self):
        self.assertEqual(_blocks("", kind="table", table_rows=((CODE, "b"),)),
                         [{"type": "table", "rows": [[{"en": f"`{CODE}`"}, {"en": "b"}]]}])

    def test_table_without_rows_gives_nothing(self):
        self.assertEqual(_blocks("", kind="table"), [])

    def test_caption_is_rich(self):
        self.assertEqual(_blocks(f"Figure 1-1. {CODE}", kind="caption"),
                         [{"type": "caption", "en": f"Figure 1-1. `{CODE}`"}])

    def test_image_names_its_file(self):
        self.assertEqual(_blocks("", kind="image", image_file="img-1.png"), [{"type": "image", "src": "img-1.png"}])

    def test_unknown_kind_gives_nothing(self):
        self.assertEqual(_blocks("x", kind="formula"), [])


if __name__ == "__main__":
    unittest.main()
