import unittest
from dataclasses import replace

from pdf_fakes import sized, span
from extraction.chapter_opener import ChapterOpener
from extraction.text_layer.layout_scan import CodeImageLinkLines, CodeListing, ProseRepairs
from extraction.text_layer.text_line import MONO_CHAR_WIDTH_RATIO, LineSpan, TextLine
from page_document import PageDocument


LINE_HEIGHT = 10.0
ORIGIN = (0.0, 0.0)


def _line(text, corner=ORIGIN):
    """Tek span'lı, metni dizilmiş düz metin satırı; corner (sol, üst) köşesi, karakter başına punto × 0.6."""
    left, top = corner
    box = (left, top, left + len(text) * LINE_HEIGHT * MONO_CHAR_WIDTH_RATIO, top + LINE_HEIGHT)
    return replace(TextLine.of([LineSpan.marked(sized(LINE_HEIGHT, span(text, box)), False)], False), text=text)


def _code_line(text, corner=ORIGIN):
    """Satır nesneleri kod satırını yalnız satırın türünden tanır."""
    return replace(_line(text, corner), is_code=True)


class PageDocumentTest(unittest.TestCase):
    PAGE = {"id": "page-2", "page": 2, "context": {"prev_tail": "gizli"},
            "blocks": [{"type": "heading", "en": "H", "tr": "B"},
                       {"type": "table", "rows": [[{"en": "a", "tr": ""}, {"en": "b", "tr": "b"}]]},
                       {"type": "code", "code": "x"}]}

    def test_text_units_skip_code(self):
        self.assertEqual([unit["en"] for unit in PageDocument(self.PAGE).text_units()], ["H", "a", "b"])

    def test_empty_translations_are_counted_as_missing(self):
        self.assertEqual(PageDocument(self.PAGE).missing_translations(), 1)


def _para(*sentences):
    return {"type": "para", "sentences": [{"en": sentence} for sentence in sentences]}


def _title():
    return {"type": "chapter", "en": "Modularity"}


class ChapterOpenerTest(unittest.TestCase):
    CHAPTER = 3
    NUMBER = {"type": "chapter_number", "num": CHAPTER}
    AUTHOR = "by Jane Doe"

    def test_number_title_and_author_become_one_block(self):
        blocks = [self.NUMBER, _title(), _para(self.AUTHOR)]
        self.assertEqual(ChapterOpener(blocks).merged(),
                         [{"type": "chapter", "en": "Modularity", "num": self.CHAPTER, "author": self.AUTHOR}])

    def test_title_without_a_number_has_an_empty_number(self):
        self.assertEqual(ChapterOpener([_title()]).merged(), [{"type": "chapter", "en": "Modularity", "num": None}])

    def test_number_without_a_title_is_dropped(self):
        self.assertEqual(ChapterOpener([self.NUMBER, _para("Body.")]).merged(), [_para("Body.")])

    def test_paragraph_after_the_title_that_is_no_author_stays_apart(self):
        merged = ChapterOpener([_title(), _para("Modules matter.")]).merged()
        self.assertEqual(merged[1:], [_para("Modules matter.")])

    def test_author_line_after_another_paragraph_stays_a_paragraph(self):
        merged = ChapterOpener([_title(), _para("Modules matter."), _para(self.AUTHOR)]).merged()
        self.assertEqual(merged[2:], [_para(self.AUTHOR)])

    def test_author_line_of_two_sentences_stays_a_paragraph(self):
        merged = ChapterOpener([_title(), _para(self.AUTHOR, "Read on.")]).merged()
        self.assertEqual(merged[1:], [_para(self.AUTHOR, "Read on.")])


class LayoutObjectsTest(unittest.TestCase):
    LEFT, TOP = 72, 100
    TWO_CHARACTERS_IN = LEFT + 2 * LINE_HEIGHT * MONO_CHAR_WIDTH_RATIO
    NEXT_LINE, AFTER_A_GAP = TOP + 12, TOP + 40

    def test_code_listing_keeps_indent_and_blank_line(self):
        lines = [_code_line("def f():", (self.LEFT, self.TOP)),
                 _code_line("return 1", (self.TWO_CHARACTERS_IN, self.NEXT_LINE)),
                 _code_line("x = f()", (self.LEFT, self.AFTER_A_GAP))]
        [listing] = CodeListing.group(lines)
        self.assertEqual(listing.region()["code"], "def f():\n  return 1\n\nx = f()")

    def test_hyphen_split_name_is_repaired(self):
        repairs = ProseRepairs([_line("published by McGraw-"), _line("Hill in 2019.")])
        self.assertEqual(repairs.hyphenated_names(), {"McGrawHill": "McGraw-Hill"})


class CodeImageLinkLinesTest(unittest.TestCase):
    """E-kitabın kod görseli bağlantısı bir satırdır; şeridi komşu satırlara kadar uzanır."""

    LINK = "Click here to view code image"
    PROSE_ABOVE = (0.0, 40)
    LINK_LINE = (0.0, 60)
    CODE_BELOW = (0.0, 80)

    def test_link_slot_reaches_the_neighbouring_lines(self):
        lines = [_line("prose", self.PROSE_ABOVE), _line(self.LINK, self.LINK_LINE),
                 _code_line("// code", self.CODE_BELOW)]
        slot = {"text": self.LINK, "y0": self.PROSE_ABOVE[1] + LINE_HEIGHT, "y1": self.CODE_BELOW[1]}
        self.assertEqual(CodeImageLinkLines(lines, self.LINK).slots(), [slot])

    def test_link_without_neighbours_keeps_its_own_height(self):
        link_top = self.LINK_LINE[1]
        self.assertEqual(CodeImageLinkLines([_line(self.LINK, self.LINK_LINE)], self.LINK).slots(),
                         [{"text": self.LINK, "y0": link_top, "y1": link_top + LINE_HEIGHT}])

    def test_line_quoting_the_link_in_prose_is_not_a_link(self):
        lines = [_line(f"you will see a “{self.LINK}” link", self.LINK_LINE)]
        self.assertEqual(CodeImageLinkLines(lines, self.LINK).slots(), [])

    def test_no_links_without_a_pattern(self):
        self.assertEqual(CodeImageLinkLines([_line(self.LINK, self.LINK_LINE)], "").slots(), [])


if __name__ == "__main__":
    unittest.main()
