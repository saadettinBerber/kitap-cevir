"""LiteParse adaptörünün kuralları. Motor çalışmaz: sahte koşucu, LiteParse'ın
kendi veri tiplerini (liteparse.types) döndürür; testler yalnız dönüşümü sınar."""
import importlib.util
import os
import tempfile
import unittest
from unittest import mock

from pdf_fakes import FAKE_PNG, FakePdfPage, span

HAS_LITEPARSE = importlib.util.find_spec("liteparse") is not None
if HAS_LITEPARSE:
    from liteparse.types import (AnnotationRect, ExtractedImage, ImageRect, LayoutBlock, LayoutCell,
                                 ParsedPage, ParseResult)
    from extraction.pdf.geometry import Box
    from extraction.pdf.liteparse_adapter import FIGURE_DPI, LiteParseLayoutReader, LiteParsePageError, plain_text

TEXT_BOX = (72, 100, 400, 114)
HEADING_WORDS = (80, 100, 200, 114)


def _rect(box):
    x0, y0, x1, y1 = box
    return AnnotationRect(x=x0, y=y0, width=x1 - x0, height=y1 - y0)


def _block(kind, **fields):
    """Kutusu verilmeyen blok metin kutusundadır; kutusuz blok için bbox=None verilir."""
    return LayoutBlock(kind=kind, **{"bbox": _rect(TEXT_BOX), **fields})


def _item(text, top):
    """Numaralı liste maddesi."""
    return _block("list_item", bbox=_rect((90, top, 300, top + 12)), text=text, ordered=True)


def _image(figure_id, path):
    return ExtractedImage(id=figure_id, name=f"img_{figure_id}.png", path=path, page=1,
                          bbox=ImageRect(x=0, y=0, width=1, height=1), width=1, height=1,
                          rotation=0.0, format="png", bytes=b"")


class FakeRunner:
    """LiteParse motorunun yerine, önceden verilen blokları döndürür."""

    def __init__(self, blocks=(), images=()):
        page = ParsedPage(page_num=1, width=595, height=800, text="", blocks=list(blocks))
        self._result = ParseResult(pages=[page], text="", images=list(images))

    def parse(self, page, image_dir):
        return self._result


class UnreadablePageRunner:
    """LiteParse'ın sayfayı okuyamadığı durum: sonuçta sayfa yoktur."""

    def parse(self, page, image_dir):
        return ParseResult(pages=[], text="", images=[])


class _ReaderTestCase(unittest.TestCase):
    """Ortak kurulum: sahte koşucuyla okuyucu, görseller geçici klasöre. Testi yoktur."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _read(self, runner, page=None):
        return LiteParseLayoutReader(runner).read(page or FakePdfPage(), self.tmp.name).elements

    def _elements(self, *blocks):
        return self._read(FakeRunner(blocks))


@unittest.skipUnless(HAS_LITEPARSE, "liteparse kurulu değil")
class BlockConversionTest(_ReaderTestCase):
    def test_consecutive_list_items_become_one_ordered_list(self):
        [bullets] = self._elements(_item("first", 100), _item("second", 114))
        self.assertEqual((bullets.kind, bullets.is_ordered), ("list", True))
        self.assertEqual([(entry.kind, entry.text) for entry in bullets.list_items],
                         [("list item", "first"), ("list item", "second")])

    def test_unordered_items_become_an_unordered_list(self):
        bullet = _block("list_item", text="dot", ordered=False)
        [bullets] = self._elements(bullet)
        self.assertFalse(bullets.is_ordered)

    def test_list_box_encloses_its_items(self):
        [bullets] = self._elements(_item("first", 100), _item("second", 114))
        self.assertEqual(bullets.box, Box(90, 100, 300, 126))

    def test_paragraph_between_items_splits_the_list(self):
        elements = self._elements(_item("a", 100), _block("paragraph", text="break"), _item("b", 140))
        self.assertEqual([element.kind for element in elements], ["list", "paragraph", "list"])

    def test_code_block_becomes_a_paragraph_of_its_lines(self):
        [paragraph] = self._elements(_block("code", lines=["System.runFinalization. They may", "increase"]))
        self.assertEqual((paragraph.kind, paragraph.text), ("paragraph", "System.runFinalization. They may increase"))

    def test_rules_and_blocks_without_a_box_are_dropped(self):
        elements = self._elements(_block("rule"), _block("paragraph", bbox=None, text="lost"),
                                  _block("paragraph", text="kept"))
        self.assertEqual([element.text for element in elements], ["kept"])

    def test_heading_text_is_plain(self):
        [heading] = self._elements(_block("heading", text="*Italic Title*", level=1))
        self.assertEqual((heading.kind, heading.text), ("heading", "Italic Title"))

    def test_table_header_becomes_the_first_row(self):
        header = [LayoutCell(text="Name"), LayoutCell(text="Kind")]
        row = [LayoutCell(text="snake\\_case"), LayoutCell(text="")]
        [table] = self._elements(_block("table", header=header, rows=[row]))
        self.assertEqual(table.table_rows, (("Name", "Kind"), ("snake_case", "")))

    def test_table_without_header_keeps_its_rows(self):
        [table] = self._elements(_block("table", rows=[[LayoutCell(text="a")]]))
        self.assertEqual(table.table_rows, (("a",),))


FIGURE_BOX = (72, 250, 272, 350)


def _unwritten_figure():
    """LiteParse'ın dosyasını yazamadığı (path'i olmayan) figür."""
    return FakeRunner([_block("figure", bbox=_rect(FIGURE_BOX), id="p1_2", format="png")], [_image("p1_2", None)])


@unittest.skipUnless(HAS_LITEPARSE, "liteparse kurulu değil")
class FigureTest(_ReaderTestCase):
    def test_written_image_keeps_its_liteparse_name(self):
        runner = FakeRunner([_block("figure", bbox=_rect(FIGURE_BOX), id="p1_1", format="png")],
                            [_image("p1_1", os.path.join(self.tmp.name, "img_p1_1.png"))])
        [image] = self._read(runner)
        self.assertEqual((image.kind, image.image_file), ("image", "img_p1_1.png"))

    def test_figure_with_a_written_image_is_not_cropped(self):
        page = FakePdfPage()
        runner = FakeRunner([_block("figure", bbox=_rect(FIGURE_BOX), id="p1_1", format="png")],
                            [_image("p1_1", os.path.join(self.tmp.name, "img_p1_1.png"))])
        with mock.patch.object(page, "png", wraps=page.png) as png:
            self._read(runner, page)
        self.assertEqual(png.call_args_list, [])

    def test_figure_without_a_written_image_is_cropped_from_the_page(self):
        [image] = self._read(_unwritten_figure())
        with open(os.path.join(self.tmp.name, image.image_file), "rb") as png:
            self.assertEqual(png.read(), FAKE_PNG)

    def test_cropped_figure_is_named_after_its_id(self):
        [image] = self._read(_unwritten_figure())
        self.assertEqual(image.image_file, "img_p1_2.png")

    def test_figure_is_cropped_at_the_figure_resolution(self):
        page = FakePdfPage()
        with mock.patch.object(page, "png", wraps=page.png) as png:
            self._read(_unwritten_figure(), page)
        self.assertEqual(png.call_args_list, [mock.call(Box(*FIGURE_BOX), FIGURE_DPI)])


@unittest.skipUnless(HAS_LITEPARSE, "liteparse kurulu değil")
class TypographyTest(_ReaderTestCase):
    """Font ve punto LiteParse'tan değil, sayfanın metin katmanından gelir."""

    def _heading_on(self, *spans):
        [heading] = self._read(FakeRunner([_block("heading", text="Title")]), FakePdfPage(lines=[spans]))
        return heading.font, heading.font_size

    def test_font_and_size_come_from_the_text_layer(self):
        self.assertEqual(self._heading_on(span("Title", (72, 100, 150, 114), "Serif-Bold", 14.4)), ("Serif-Bold", 14.4))

    def test_the_font_with_most_characters_wins(self):
        mark = span("a", (72, 100, 78, 114), "Serif", 6.0)
        words = span("Long heading", HEADING_WORDS, "Serif-Bold", 14.4)
        self.assertEqual(self._heading_on(mark, words), ("Serif-Bold", 14.4))

    def test_blanks_do_not_weigh(self):
        padded = span("  a      ", (72, 100, 78, 114), "Serif", 6.0)
        words = span("bc", HEADING_WORDS, "Serif-Bold", 14.4)
        self.assertEqual(self._heading_on(padded, words), ("Serif-Bold", 14.4))

    def test_span_centred_on_the_box_edge_is_outside(self):
        self.assertEqual(self._heading_on(span("x", (390, 100, 410, 114), "Serif", 9.0)), ("", 0.0))

    def test_box_without_spans_has_no_typography(self):
        self.assertEqual(self._heading_on(), ("", 0.0))


@unittest.skipUnless(HAS_LITEPARSE, "liteparse kurulu değil")
class UnreadablePageTest(_ReaderTestCase):
    def test_page_liteparse_cannot_read_raises(self):
        with self.assertRaises(LiteParsePageError):
            self._read(UnreadablePageRunner())


@unittest.skipUnless(HAS_LITEPARSE, "liteparse kurulu değil")
class PlainTextTest(unittest.TestCase):
    def test_whole_line_emphasis_is_removed(self):
        self.assertEqual(plain_text("*Short italic lead* and plain."), "Short italic lead and plain.")
        self.assertEqual(plain_text("**Bold line** then more."), "Bold line then more.")

    def test_adjacent_bold_italic_runs_are_removed(self):
        self.assertEqual(plain_text("***token.*** **the length**"), "token. the length")

    def test_escaped_characters_stay_literal(self):
        self.assertEqual(plain_text("a \\* b, snake\\_case, C:\\\\temp"), "a * b, snake_case, C:\\temp")

    def test_escaped_stars_are_not_emphasis(self):
        self.assertEqual(plain_text("\\*\\*not bold\\*\\*"), "**not bold**")

    def test_backticks_stay_as_inline_code_marks(self):
        self.assertEqual(plain_text("methods `System.gc` and"), "methods `System.gc` and")


if __name__ == "__main__":
    unittest.main()
