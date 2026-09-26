import dataclasses
import unittest

from pdf_fakes import PAGE_HEIGHT, FakeLayoutReader, FakePdfPage, element, span
from extraction.block_builder import BlockBuilder
from extraction.layout_elements import LayoutFixer
from extraction.page_extractor import PageExtractor
from extraction.page_regions import PageRegions, Region
from extraction.pdf.model import PageLayout
from extraction.page_zones import InvalidRunningHeader, PageZones
from extraction.settings import DEFAULT_EXTRACTION, with_defaults

# Kutular sol-üst orijinli, sayfa 800 punto. Bölge ayarları alt kenardan ölçülür:
# alt bilgi çizgisi 800 - 52 = 748, varsayılan başlık çizgisi 800 - 610 = 190.
FOOTER_TOP = 52
BODY_Y = (70, 280, 430, 300)
FOOTER_Y = (70, 752, 430, 762)
PAGE_TOP_Y = (70, 80, 430, 100)
HEADER_ZONE_Y = (70, 160, 430, 180)
ABOVE_PAGE_TOP_Y = (70, 60, 430, 80)
JUST_ABOVE_FOOTER_Y = (70, 740, 430, 752)
FOOTER_LINE = PAGE_HEIGHT - FOOTER_TOP
LINE_HEIGHT = 10


BODY_FONT_SIZE = 10.5
STEP = 0.1


def _element(content, box):
    return dataclasses.replace(element(content, box), font_size=BODY_FONT_SIZE)


def _starting_at(top):
    return (BODY_Y[0], top, BODY_Y[2], top + LINE_HEIGHT)


def _split(zones, elements):
    return zones.split(PageLayout(PAGE_HEIGHT, tuple(elements)))


class PlainFixer:
    """TextFixer'ın testte gereken tek davranışı: metni olduğu gibi döndürmek."""

    def plain(self, text):
        return text or ""

    def rich(self, text):
        return text


def _settings(**overrides):
    return with_defaults({"footer_zone_top": FOOTER_TOP, **overrides})


DEFAULTS = _settings()
BOTTOM_HEADER = _settings(running_header="bottom")
NO_HEADER = _settings(running_header="none")


def _builder(settings):
    return BlockBuilder(settings, PlainFixer())


class BottomRunningHeaderTest(unittest.TestCase):
    """O'Reilly dizgisinde koşu başlığı sayfanın altındadır."""

    TALL = (70, 150, 430, 200)

    FOOTER = "Preventing Data Loss | 201"

    def test_section_name_is_read_from_the_footer(self):
        header, _ = _split(PageZones(BOTTOM_HEADER), [_element("Body text", BODY_Y), _element(self.FOOTER, FOOTER_Y)])
        self.assertEqual(header, {"text": "Preventing Data Loss", "is_chapter": False})

    def test_footer_holding_the_header_leaves_the_body(self):
        _, body = _split(PageZones(BOTTOM_HEADER), [_element("Body text", BODY_Y), _element(self.FOOTER, FOOTER_Y)])
        self.assertEqual([element.text for element in body], ["Body text"])

    def test_footer_split_into_separate_elements_is_joined(self):
        elements = [_element("Measuring Modularity", FOOTER_Y),
                    _element("|", FOOTER_Y), _element("41", FOOTER_Y)]
        header, _ = _split(PageZones(BOTTOM_HEADER), elements)
        self.assertEqual(header["text"], "Measuring Modularity")

    def test_chapter_footer_is_marked_as_chapter(self):
        elements = [_element("200 | Chapter 14: Event-Driven Architecture Style", FOOTER_Y)]
        header, _ = _split(PageZones(BOTTOM_HEADER), elements)
        self.assertTrue(header["is_chapter"])

    def test_page_number_alone_means_chapter_opening(self):
        header, _ = _split(PageZones(BOTTOM_HEADER), [_element("1", FOOTER_Y)])
        self.assertIsNone(header)

    def test_element_starting_on_the_footer_line_is_no_header(self):
        header, _ = _split(PageZones(BOTTOM_HEADER), [_element(self.FOOTER, _starting_at(FOOTER_LINE))])
        self.assertIsNone(header)

    def test_top_header_is_unchanged_by_default(self):
        top = _element("Chapter 3: Modularity 41", HEADER_ZONE_Y)
        header, _ = _split(PageZones(DEFAULTS), [top, _element("Body", BODY_Y)])
        self.assertEqual(header["text"], "Chapter 3: Modularity")

    def test_top_header_leaves_the_body(self):
        top = _element("Chapter 3: Modularity 41", HEADER_ZONE_Y)
        _, body = _split(PageZones(DEFAULTS), [top, _element("Body", BODY_Y)])
        self.assertEqual([element.text for element in body], ["Body"])

    def test_top_header_takes_only_the_first_element_in_its_zone(self):
        top = _element("Chapter 3: Modularity 41", ABOVE_PAGE_TOP_Y)
        carried = _element("continued paragraph", PAGE_TOP_Y)
        _, body = _split(PageZones(DEFAULTS), [top, carried])
        self.assertEqual([element.text for element in body], ["continued paragraph"])

    def test_element_reaching_below_the_header_line_is_no_header(self):
        header, _ = _split(PageZones(DEFAULTS), [_element("Paragraph that starts high", self.TALL)])
        self.assertIsNone(header)

    def test_element_reaching_below_the_header_line_is_body(self):
        tall = _element("Paragraph that starts high", self.TALL)
        _, body = _split(PageZones(DEFAULTS), [tall])
        self.assertEqual(body, [tall])


class NoRunningHeaderTest(unittest.TestCase):
    """E-kitap kökenli PDF'lerde (Effective Java) koşu başlığı yoktur: sayfanın
    en üstündeki öğe önceki sayfadan süren paragraf ya da tablo satırıdır."""

    CARRIED = "to be avoided. Such examples..."

    def test_first_element_at_page_top_is_no_header(self):
        header, _ = _split(PageZones(NO_HEADER), [_element(self.CARRIED, PAGE_TOP_Y), _element("Body", BODY_Y)])
        self.assertIsNone(header)

    def test_first_element_at_page_top_stays_in_body(self):
        _, body = _split(PageZones(NO_HEADER), [_element(self.CARRIED, PAGE_TOP_Y), _element("Body", BODY_Y)])
        self.assertEqual([element.text for element in body], [self.CARRIED, "Body"])

    def test_footer_is_still_dropped(self):
        _, body = _split(PageZones(NO_HEADER), [_element("Body", BODY_Y), _element("21", FOOTER_Y)])
        self.assertEqual([element.text for element in body], ["Body"])

    def test_element_starting_above_the_footer_line_is_body(self):
        closing = _element("Last line", JUST_ABOVE_FOOTER_Y)
        _, body = _split(PageZones(NO_HEADER), [closing])
        self.assertEqual(body, [closing])

    def test_element_starting_on_the_footer_line_is_body(self):
        closing = _element("Last line", _starting_at(FOOTER_LINE))
        _, body = _split(PageZones(NO_HEADER), [closing])
        self.assertEqual(body, [closing])

    def test_element_starting_just_below_the_footer_line_is_footer(self):
        _, body = _split(PageZones(NO_HEADER), [_element("21", _starting_at(FOOTER_LINE + STEP))])
        self.assertEqual(body, [])


class RunningHeaderSettingTest(unittest.TestCase):
    """running_header yalnız top / bottom / none olabilir; yanlış ayar sessizce
    gövde metni yutmasın diye kurulumda reddedilir."""

    def test_unknown_position_is_rejected(self):
        with self.assertRaises(InvalidRunningHeader):
            PageZones(_settings(running_header="left"))

    def test_removed_header_at_bottom_setting_names_its_replacement(self):
        with self.assertRaisesRegex(InvalidRunningHeader, "running_header"):
            PageZones(_settings(header_at_bottom=True))


class ChapterLabelTest(unittest.TestCase):
    """Bölüm açılışındaki "CHAPTER 7" satırı bölüm numarasıdır, paragraf değil."""

    LABELLED = _settings(chapter_label_pattern=r"^CHAPTER (\d+)$")
    CHAPTER = 7

    def test_label_becomes_chapter_number_block(self):
        blocks = _builder(self.LABELLED).blocks_of(_element(f"CHAPTER {self.CHAPTER}", BODY_Y))
        self.assertEqual(blocks, [{"type": "chapter_number", "num": self.CHAPTER}])

    def test_other_paragraphs_are_untouched(self):
        blocks = _builder(self.LABELLED).blocks_of(_element("CHAPTER 7 covers modularity.", BODY_Y))
        self.assertEqual(blocks[0]["type"], "para")

    def test_pattern_is_disabled_by_default(self):
        blocks = _builder(DEFAULTS).blocks_of(_element("CHAPTER 7", BODY_Y))
        self.assertEqual(blocks[0]["type"], "para")


class HeadingBySizeTest(unittest.TestCase):
    """Başlığı puntosu ele verir; okuyucu onu paragraf sansa da."""

    CHAPTER_SIZE = DEFAULT_EXTRACTION["chapter_title_min_size"]

    @staticmethod
    def _blocks(text, **fields):
        return _builder(DEFAULTS).blocks_of(dataclasses.replace(element(text, BODY_Y), **fields))

    def test_paragraph_at_chapter_title_size_is_the_chapter(self):
        self.assertEqual(self._blocks("Chapter 1. Introduction", font_size=self.CHAPTER_SIZE),
                         [{"type": "chapter", "en": "Chapter 1. Introduction"}])

    def test_paragraph_just_below_chapter_size_stays_a_paragraph(self):
        self.assertEqual(self._blocks("Chapter 1. Introduction", font_size=self.CHAPTER_SIZE - STEP)[0]["type"], "para")

    def test_large_sentence_is_still_a_paragraph(self):
        self.assertEqual(self._blocks("A large opening sentence.", font_size=self.CHAPTER_SIZE)[0]["type"], "para")

    def test_nested_element_needs_only_subsection_size(self):
        size = DEFAULT_EXTRACTION["subsection_min_size"]
        self.assertEqual(self._blocks("Cross-Cutting", font_size=size, is_nested=True)[0]["type"], "heading")

    def test_nested_element_just_below_subsection_size_stays_a_paragraph(self):
        size = DEFAULT_EXTRACTION["subsection_min_size"] - STEP
        self.assertEqual(self._blocks("Cross-Cutting", font_size=size, is_nested=True)[0]["type"], "para")




class CodeImageLinkPlacementTest(unittest.TestCase):
    """Bağlantısından arınan tek satırlık kod listesi kod bölgesine düşer."""

    LINK = "Click here to view code image"
    SLOT = {"text": LINK, "y0": 50, "y1": 80}
    CODE_LINE = {"y0": 80, "y1": 90}
    LINK_WITH_CODE_BELOW = (70, 60, 430, 90)

    def test_one_line_listing_glued_under_the_link_is_placed_as_code(self):
        code = {"type": "code", "lang": "java", "code": "// Two classes"}
        regions = PageRegions([Region({**self.CODE_LINE, "block": code})])
        glued = _element(f"{self.LINK} // Two classes", self.LINK_WITH_CODE_BELOW)
        body = LayoutFixer([], [self.SLOT]).fixed([glued]).elements
        self.assertEqual(regions.place(body, _builder(DEFAULTS).blocks_of), [code])



class PageExtractorTest(unittest.TestCase):
    """Satır sonunda bölünen özel isim, metin katmanından onarılır ('McGraw-' + 'Hill')."""

    def test_hyphen_fixes_come_from_the_text_layer(self):
        page = FakePdfPage(lines=[(span("published by McGraw-", PAGE_TOP_Y),), (span("Hill in 2019.", BODY_Y),)])
        fixes = PageExtractor(DEFAULTS, FakeLayoutReader()).hyphen_fixes(page)
        self.assertEqual(fixes, {"McGrawHill": "McGraw-Hill"})


if __name__ == "__main__":
    unittest.main()
