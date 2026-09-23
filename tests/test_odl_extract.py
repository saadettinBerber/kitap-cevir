import unittest

import _paths  # noqa: F401
from extraction.block_builder import BlockBuilder
from extraction.page_zones import InvalidRunningHeader, PageZones
from project import DEFAULT_EXTRACTION

FOOTER_TOP = 52
BODY_Y = (70, 500, 430, 520)
FOOTER_Y = (70, 38, 430, 48)
PAGE_TOP_Y = (70, 700, 430, 720)


BODY_FONT_SIZE = 10.5


def _element(content, box, kind="paragraph"):
    return {"type": kind, "content": content, "bounding box": list(box),
            "font size": BODY_FONT_SIZE}


class PlainFixer:
    """TextFixer'ın testte gereken tek davranışı: metni olduğu gibi döndürmek."""

    def plain(self, text):
        return text or ""

    def rich(self, text):
        return text


def _settings(**overrides):
    return {**DEFAULT_EXTRACTION, "footer_zone_top": FOOTER_TOP, **overrides}


def _zones(**overrides):
    return PageZones(_settings(**overrides))


def _builder(**overrides):
    return BlockBuilder(_settings(**overrides), PlainFixer())


class BottomRunningHeaderTest(unittest.TestCase):
    """O'Reilly dizgisinde koşu başlığı sayfanın altındadır."""

    def test_section_name_is_read_from_the_footer(self):
        elements = [_element("Body text", BODY_Y),
                    _element("Preventing Data Loss | 201", FOOTER_Y)]
        header, body = _zones(running_header="bottom").split(elements)
        self.assertEqual(header, {"text": "Preventing Data Loss", "is_chapter": False})
        self.assertEqual([element["content"] for element in body], ["Body text"])

    def test_footer_split_into_separate_elements_is_joined(self):
        elements = [_element("Measuring Modularity", FOOTER_Y),
                    _element("|", FOOTER_Y), _element("41", FOOTER_Y)]
        header, _ = _zones(running_header="bottom").split(elements)
        self.assertEqual(header["text"], "Measuring Modularity")

    def test_chapter_footer_is_marked_as_chapter(self):
        elements = [_element("200 | Chapter 14: Event-Driven Architecture Style", FOOTER_Y)]
        header, _ = _zones(running_header="bottom").split(elements)
        self.assertTrue(header["is_chapter"])

    def test_page_number_alone_means_chapter_opening(self):
        header, _ = _zones(running_header="bottom").split([_element("1", FOOTER_Y)])
        self.assertIsNone(header)

    def test_top_header_is_unchanged_by_default(self):
        top = _element("Chapter 3: Modularity 41", (70, 620, 430, 640))
        header, body = _zones().split([top, _element("Body", BODY_Y)])
        self.assertEqual(header["text"], "Chapter 3: Modularity")
        self.assertEqual(len(body), 1)

    def test_top_header_takes_only_the_first_element_in_its_zone(self):
        top = _element("Chapter 3: Modularity 41", (70, 720, 430, 740))
        carried = _element("continued paragraph", PAGE_TOP_Y)
        _, body = _zones().split([top, carried])
        self.assertEqual([element["content"] for element in body], ["continued paragraph"])


class NoRunningHeaderTest(unittest.TestCase):
    """E-kitap kökenli PDF'lerde (Effective Java) koşu başlığı yoktur: sayfanın
    en üstündeki öğe önceki sayfadan süren paragraf ya da tablo satırıdır."""

    def test_first_element_at_page_top_stays_in_body(self):
        carried = _element("to be avoided. Such examples...", PAGE_TOP_Y)
        header, body = _zones(running_header="none").split([carried, _element("Body", BODY_Y)])
        self.assertIsNone(header)
        self.assertEqual([element["content"] for element in body], ["to be avoided. Such examples...", "Body"])

    def test_footer_is_still_dropped(self):
        _, body = _zones(running_header="none").split([_element("Body", BODY_Y), _element("21", FOOTER_Y)])
        self.assertEqual([element["content"] for element in body], ["Body"])


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


if __name__ == "__main__":
    unittest.main()
