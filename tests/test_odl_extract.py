import unittest

from pdf_fakes import PAGE_HEIGHT, element
from extraction.block_builder import BlockBuilder
from extraction.layout_elements import LayoutElements
from extraction.page_regions import PageRegions, Region
from extraction.pdf.geometry import Box
from extraction.pdf.model import PageLayout
from extraction.page_zones import InvalidRunningHeader, PageZones
from extraction.settings import DEFAULT_EXTRACTION, with_defaults

# Kutular sol-üst orijinli, sayfa 800 punto. Bölge ayarları alt kenardan ölçülür:
# alt bilgi çizgisi 800 - 52 = 748, varsayılan başlık çizgisi 800 - 610 = 190.
FOOTER_TOP = 52
BODY_Y = (70, 280, 430, 300)
FOOTER_Y = (70, 752, 430, 762)
PAGE_TOP_Y = (70, 80, 430, 100)


BODY_FONT_SIZE = 10.5


def _element(content, box, kind="paragraph"):
    return element(content, box, kind, font_size=BODY_FONT_SIZE)


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


def _zones(**overrides):
    return PageZones(_settings(**overrides))


def _builder(**overrides):
    return BlockBuilder(_settings(**overrides), PlainFixer())


class BottomRunningHeaderTest(unittest.TestCase):
    """O'Reilly dizgisinde koşu başlığı sayfanın altındadır."""

    def test_section_name_is_read_from_the_footer(self):
        elements = [_element("Body text", BODY_Y),
                    _element("Preventing Data Loss | 201", FOOTER_Y)]
        header, body = _split(_zones(running_header="bottom"), elements)
        self.assertEqual(header, {"text": "Preventing Data Loss", "is_chapter": False})
        self.assertEqual([element.text for element in body], ["Body text"])

    def test_footer_split_into_separate_elements_is_joined(self):
        elements = [_element("Measuring Modularity", FOOTER_Y),
                    _element("|", FOOTER_Y), _element("41", FOOTER_Y)]
        header, _ = _split(_zones(running_header="bottom"), elements)
        self.assertEqual(header["text"], "Measuring Modularity")

    def test_chapter_footer_is_marked_as_chapter(self):
        elements = [_element("200 | Chapter 14: Event-Driven Architecture Style", FOOTER_Y)]
        header, _ = _split(_zones(running_header="bottom"), elements)
        self.assertTrue(header["is_chapter"])

    def test_page_number_alone_means_chapter_opening(self):
        header, _ = _split(_zones(running_header="bottom"), [_element("1", FOOTER_Y)])
        self.assertIsNone(header)

    def test_top_header_is_unchanged_by_default(self):
        top = _element("Chapter 3: Modularity 41", (70, 160, 430, 180))
        header, body = _split(_zones(), [top, _element("Body", BODY_Y)])
        self.assertEqual(header["text"], "Chapter 3: Modularity")
        self.assertEqual(len(body), 1)

    def test_top_header_takes_only_the_first_element_in_its_zone(self):
        top = _element("Chapter 3: Modularity 41", (70, 60, 430, 80))
        carried = _element("continued paragraph", PAGE_TOP_Y)
        _, body = _split(_zones(), [top, carried])
        self.assertEqual([element.text for element in body], ["continued paragraph"])

    def test_element_reaching_below_the_header_line_is_body(self):
        tall = _element("Paragraph that starts high", (70, 150, 430, 200))
        header, body = _split(_zones(), [tall])
        self.assertIsNone(header)
        self.assertEqual(body, [tall])


class NoRunningHeaderTest(unittest.TestCase):
    """E-kitap kökenli PDF'lerde (Effective Java) koşu başlığı yoktur: sayfanın
    en üstündeki öğe önceki sayfadan süren paragraf ya da tablo satırıdır."""

    def test_first_element_at_page_top_stays_in_body(self):
        carried = _element("to be avoided. Such examples...", PAGE_TOP_Y)
        header, body = _split(_zones(running_header="none"), [carried, _element("Body", BODY_Y)])
        self.assertIsNone(header)
        self.assertEqual([element.text for element in body], ["to be avoided. Such examples...", "Body"])

    def test_footer_is_still_dropped(self):
        _, body = _split(_zones(running_header="none"), [_element("Body", BODY_Y), _element("21", FOOTER_Y)])
        self.assertEqual([element.text for element in body], ["Body"])

    def test_element_starting_above_the_footer_line_is_body(self):
        closing = _element("Last line", (70, 740, 430, 752))
        _, body = _split(_zones(running_header="none"), [closing])
        self.assertEqual(body, [closing])


class RunningHeaderSettingTest(unittest.TestCase):
    """running_header yalnız top / bottom / none olabilir; yanlış ayar sessizce
    gövde metni yutmasın diye kurulumda reddedilir."""

    def test_unknown_position_is_rejected(self):
        with self.assertRaises(InvalidRunningHeader):
            _zones(running_header="left")

    def test_removed_header_at_bottom_setting_names_its_replacement(self):
        with self.assertRaisesRegex(InvalidRunningHeader, "running_header"):
            _zones(header_at_bottom=True)


class ChapterLabelTest(unittest.TestCase):
    """Bölüm açılışındaki "CHAPTER 7" satırı bölüm numarasıdır, paragraf değil."""

    PATTERN = r"^CHAPTER (\d+)$"

    def test_label_becomes_chapter_number_block(self):
        blocks = _builder(chapter_label_pattern=self.PATTERN).blocks_of(_element("CHAPTER 7", BODY_Y))
        self.assertEqual(blocks, [{"type": "chapter_number", "num": 7}])

    def test_other_paragraphs_are_untouched(self):
        blocks = _builder(chapter_label_pattern=self.PATTERN).blocks_of(_element("CHAPTER 7 covers modularity.", BODY_Y))
        self.assertEqual(blocks[0]["type"], "para")

    def test_pattern_is_disabled_by_default(self):
        blocks = _builder().blocks_of(_element("CHAPTER 7", BODY_Y))
        self.assertEqual(blocks[0]["type"], "para")


class HeadingBySizeTest(unittest.TestCase):
    """Başlığı puntosu ele verir; okuyucu onu paragraf sansa da."""

    CHAPTER_SIZE = DEFAULT_EXTRACTION["chapter_title_min_size"]

    def _blocks(self, text, size, **fields):
        return _builder().blocks_of(element(text, BODY_Y, font_size=size, **fields))

    def test_paragraph_at_chapter_title_size_is_the_chapter(self):
        self.assertEqual(self._blocks("Chapter 1. Introduction", self.CHAPTER_SIZE),
                         [{"type": "chapter", "en": "Chapter 1. Introduction"}])

    def test_paragraph_just_below_chapter_size_stays_a_paragraph(self):
        self.assertEqual(self._blocks("Chapter 1. Introduction", self.CHAPTER_SIZE - 0.1)[0]["type"], "para")

    def test_large_sentence_is_still_a_paragraph(self):
        self.assertEqual(self._blocks("A large opening sentence.", self.CHAPTER_SIZE)[0]["type"], "para")

    def test_nested_element_needs_only_subsection_size(self):
        size = DEFAULT_EXTRACTION["subsection_min_size"]
        self.assertEqual(self._blocks("Cross-Cutting", size, is_nested=True)[0]["type"], "heading")


class CodeImageLinkTest(unittest.TestCase):
    """E-kitap kökenli PDF'lerde her kod listesinin üstünde bir bağlantı satırı
    vardır; kitabın içeriği değildir. ODL onu komşu satırla tek öğede birleştirebilir."""

    LINK = "Click here to view code image"
    # Bağlantı satırı 60-70'te, şeridi komşu satırlara kadar 50-80; kod satırı 80-90.
    SLOT = {"text": LINK, "y0": 50, "y1": 80}
    CODE_LINE = {"y0": 80, "y1": 90}

    def _without_links(self, *elements):
        return LayoutElements(list(elements)).without_code_image_links([self.SLOT]).items

    def test_element_that_is_only_the_link_is_dropped(self):
        self.assertEqual(self._without_links(_element(self.LINK, (70, 60, 430, 70), "heading")), [])

    def test_code_glued_under_the_link_keeps_its_text_and_loses_the_slot(self):
        [element] = self._without_links(_element(f"{self.LINK} // Two classes", (70, 60, 430, 90)))
        self.assertEqual(element.text, "// Two classes")
        self.assertEqual(element.box, Box(70, 80, 430, 90))

    def test_one_line_listing_glued_under_the_link_is_placed_as_code(self):
        code = {"type": "code", "lang": "java", "code": "// Two classes"}
        regions = PageRegions([Region(self.CODE_LINE, code)])
        glued = _element(f"{self.LINK} // Two classes", (70, 60, 430, 90))
        self.assertEqual(regions.place(self._without_links(glued), _builder().blocks_of), [code])

    def test_prose_glued_above_the_link_is_kept_above_the_slot(self):
        [element] = self._without_links(_element(f"reduces the time to 9.2 seconds: {self.LINK}", (70, 20, 430, 70)))
        self.assertEqual(element.text, "reduces the time to 9.2 seconds:")
        self.assertEqual(element.box, Box(70, 20, 430, 50))

    def test_elements_away_from_the_link_are_untouched(self):
        body, image = _element("Body text", BODY_Y), element("", (70, 500, 430, 700), "image")
        self.assertEqual(self._without_links(body, image), [body, image])


if __name__ == "__main__":
    unittest.main()
