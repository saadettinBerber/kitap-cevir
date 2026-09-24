"""LiteParse öğrenme testleri (Bl.8 · Learning Tests).

Kodumuzu değil, LiteParse adaptörünün dayandığı kütüphane davranışını sınar.
LiteParse yükseltildiğinde bir varsayım bozulursa hata kitap çıktısında değil
burada görünür. Sayfa, üretimdeki ayarlarla (LiteParseRunner) bir kez okunur.

Blok yapısı da sabitlenir: satır içi denklem, komşu kelimelerini aynı blokta
arar. LiteParse bir liste maddesine ardından gelen paragrafı katınca ya da
hizalı bir bölgeyi tek tabloya çevirince komşu başka bloğa düşer ve denklem
atlanır (ai-engineering 236 ve 31). Bu davranış değişirse buradan duyulur.

Testle sabitlenemeyen bir bulgu: LiteParse'ın puntosu kimi PDF'te metin
katmanından farklıdır (Effective Java'da 20, PyMuPDF ve ODL'de 14.4). Bu yüzden
adaptör font ve puntoyu PdfPage'den alır.
"""
import importlib.util
import os
import tempfile
import unittest

import fitz

from pdf_fakes import real_page

HAS_LITEPARSE = importlib.util.find_spec("liteparse") is not None
if HAS_LITEPARSE:
    from extraction.pdf.liteparse_adapter import LiteParseRunner

BODY_SIZE = 11
LIST_STEPS = ("First step of the list", "Second step of the list", "Third step of the list")
FOOTER = "Learning Tests | 42"
LINE_STEP = 14
LAST_ITEM_BASELINE = 156
FOLDED_PARAGRAPH = "Entropy and cross entropy share one notation."
SEPARATE_PARAGRAPH = "Cross entropy is not symmetric."
TABLE_ROWS = (("Human a", ("Interpreters and translators", "Survey researchers", "Poets and writers"),
               ("76.5", "75.0", "68.8")),
              ("Human b", ("Survey researchers", "Writers and authors", "Animal scientists"),
               ("84.4", "82.5", "82.4")))
TABLE_ROW_GAP = 14
TABLE_HEADER_BASELINE = 120


class _Writer:
    """Test sayfasını satır satır yazar; satır içinde font değişebilir."""

    def __init__(self, page):
        self.page = page

    def line(self, y, *parts, x=72):
        for text, font in parts:
            self.page.insert_text((x, y), text, fontsize=BODY_SIZE, fontname=font)
            x += fitz.get_text_length(text, font, BODY_SIZE)


def _write_pdf(path, write_page):
    document = fitz.open()
    write_page(document.new_page())
    document.save(path)
    document.close()


def _write_learning_page(page):
    write = _Writer(page)
    page.insert_text((72, 80), "Learning Boundaries", fontsize=20, fontname="helvetica-bold")
    write.line(120, ("A paragraph with a ", "helv"), ("bold", "helvetica-bold"), (" word inside it.", "helv"))
    for index, step in enumerate(LIST_STEPS):
        write.line(170 + 16 * index, (f"{index + 1}. {step}", "helv"))
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 20), 0)
    page.insert_image(fitz.Rect(72, 250, 272, 350), pixmap=pixmap)
    write.line(400, ("Short italic lead", "helvetica-oblique"))
    write.line(414, ("and plain continuation text.", "helv"))
    write.line(450, ("Multiply a * b, name snake_case in C:\\temp.", "helv"))
    write.line(520, ("Quote `pair` of backticks.", "helv"))
    page.insert_text((300, 800), FOOTER, fontsize=9, fontname="helv")


def _write_list_page(page):
    """Asılı girintili iki madde; hemen altında bir paragraf, açık bir boşluktan sonra bir paragraf daha."""
    write = _Writer(page)
    write.line(80, ("Cross entropy depends on two qualities:", "helv"))
    write.line(110, ("1. The predictability of the training data,", "helv"), x=86)
    write.line(124, ("measured by its entropy", "helv"), x=100)
    write.line(142, ("2. How far the learned distribution", "helv"), x=86)
    write.line(LAST_ITEM_BASELINE, ("diverges from the true one", "helv"), x=100)
    write.line(LAST_ITEM_BASELINE + LINE_STEP + 4, (FOLDED_PARAGRAPH, "helv"), x=100)
    write.line(LAST_ITEM_BASELINE + 5 * LINE_STEP, (SEPARATE_PARAGRAPH, "helv"))


def _write_table_page(page):
    """Başlık satırı kalın üç sütun; meslek ve değer hücreleri üçer satırdır (iki satırlıkta tablo çıkmaz)."""
    write = _Writer(page)
    write.line(80, ("Table 1-2. Occupations with the highest exposure to AI.", "helv"))
    for x, header in ((78, "Group"), (180, "Occupations"), (420, "% Exposure")):
        write.line(TABLE_HEADER_BASELINE, (header, "helvetica-bold"), x=x)
    y = TABLE_HEADER_BASELINE + 2 * LINE_STEP
    for group, occupations, values in TABLE_ROWS:
        write.line(y, (group, "helv"), x=78)
        for occupation, value in zip(occupations, values):
            write.line(y, (occupation, "helv"), x=180)
            write.line(y, (value, "helv"), x=420)
            y += LINE_STEP
        y += TABLE_ROW_GAP


class _ParsedPage:
    """TEMPLATE METHOD: alt sınıfın write_page'i sayfayı yazar, LiteParse onu üretimdeki ayarlarla bir kez okur."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.images = os.path.join(cls.tmp.name, "images")
        pdf = os.path.join(cls.tmp.name, "learning.pdf")
        _write_pdf(pdf, cls.write_page)
        with real_page(pdf) as page:
            cls.page_height, cls.text_lines = page.height, page.text_lines()
            cls.result = LiteParseRunner().parse(page, cls.images)
        cls.parsed = cls.result.pages[0]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _blocks(self, kind):
        return [block for block in self.parsed.blocks if block.kind == kind]


@unittest.skipUnless(HAS_LITEPARSE, "liteparse kurulu değil")
class LiteParseLearningTest(_ParsedPage, unittest.TestCase):
    write_page = staticmethod(_write_learning_page)

    def _text_of(self, prefix):
        return next(block.text for block in self.parsed.blocks if (block.text or "").lstrip("*").startswith(prefix))

    def test_page_size_matches_the_text_layer(self):
        self.assertEqual(self.parsed.height, self.page_height)

    def test_boxes_are_top_left_points_close_to_the_text_layer(self):
        heading, title_span = self._blocks("heading")[0].bbox, self.text_lines[0][0].box
        self.assertEqual(heading.x, title_span.x0)
        self.assertAlmostEqual(heading.y, title_span.y0, delta=3)

    def test_blocks_come_in_reading_order(self):
        kinds = [block.kind for block in self.parsed.blocks]
        self.assertEqual(kinds[:6], ["heading", "paragraph", "list_item", "list_item", "list_item", "figure"])

    def test_list_items_arrive_one_by_one_without_a_container(self):
        items = self._blocks("list_item")
        self.assertEqual([item.text for item in items], list(LIST_STEPS))
        self.assertTrue(all(item.ordered for item in items))
        self.assertEqual(self._blocks("list"), [])

    def test_list_marker_is_kept_apart_from_the_text(self):
        self.assertEqual([item.marker for item in self._blocks("list_item")], ["1.", "2.", "3."])

    def test_bold_word_inside_a_line_is_not_marked(self):
        self.assertEqual(self._text_of("A paragraph"), "A paragraph with a bold word inside it.")

    def test_whole_italic_line_is_wrapped_in_asterisks(self):
        self.assertEqual(self._text_of("Short italic"), "*Short italic lead* and plain continuation text.")

    def test_literal_markdown_characters_are_escaped(self):
        self.assertEqual(self._text_of("Multiply"), "Multiply a \\* b, name snake\\_case in C:\\\\temp.")

    def test_backticks_pass_through_unescaped(self):
        self.assertEqual(self._text_of("Quote"), "Quote `pair` of backticks.")

    def test_figure_id_names_the_image_written_to_image_dir(self):
        [figure], [image] = self._blocks("figure"), self.result.images
        self.assertEqual((image.id, image.name), (figure.id, f"img_{figure.id}.{figure.format}"))
        self.assertTrue(os.path.isfile(os.path.join(self.images, image.name)))

    def test_single_page_parse_keeps_the_running_footer(self):
        self.assertEqual(self.parsed.blocks[-1].text, FOOTER)


@unittest.skipUnless(HAS_LITEPARSE, "liteparse kurulu değil")
class ListContinuationTest(_ParsedPage, unittest.TestCase):
    write_page = staticmethod(_write_list_page)

    def test_paragraph_right_under_a_list_item_is_folded_into_it(self):
        self.assertTrue(self._blocks("list_item")[-1].text.endswith(FOLDED_PARAGRAPH))

    def test_paragraph_after_a_clear_gap_stays_apart(self):
        self.assertEqual([block.text for block in self._blocks("paragraph")][-1], SEPARATE_PARAGRAPH)


@unittest.skipUnless(HAS_LITEPARSE, "liteparse kurulu değil")
class AlignedColumnsTest(_ParsedPage, unittest.TestCase):
    write_page = staticmethod(_write_table_page)

    def test_aligned_columns_come_back_as_one_table(self):
        self.assertEqual(len(self._blocks("table")), 1)

    def test_table_starts_at_the_header(self):
        header = self.text_lines[1][0].box
        self.assertLess(self._blocks("table")[0].bbox.y, header.y1)

    def test_table_reaches_the_last_row(self):
        box, last_row = self._blocks("table")[0].bbox, self.text_lines[-1][0].box
        self.assertGreater(box.y + box.height, last_row.y0)


if __name__ == "__main__":
    unittest.main()
