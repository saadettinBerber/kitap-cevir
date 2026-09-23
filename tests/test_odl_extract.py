import unittest

import _paths  # noqa: F401
from block_builder import BlockBuilder
from page_zones import PageZones
from project import DEFAULT_EXTRACTION

FOOTER_TOP = 52
BODY_Y = (70, 500, 430, 520)
FOOTER_Y = (70, 38, 430, 48)


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
        header, body = _zones(header_at_bottom=True).split(elements)
        self.assertEqual(header, {"text": "Preventing Data Loss", "is_chapter": False})
        self.assertEqual([element["content"] for element in body], ["Body text"])

    def test_footer_split_into_separate_elements_is_joined(self):
        elements = [_element("Measuring Modularity", FOOTER_Y),
                    _element("|", FOOTER_Y), _element("41", FOOTER_Y)]
        header, _ = _zones(header_at_bottom=True).split(elements)
        self.assertEqual(header["text"], "Measuring Modularity")

    def test_chapter_footer_is_marked_as_chapter(self):
        elements = [_element("200 | Chapter 14: Event-Driven Architecture Style", FOOTER_Y)]
        header, _ = _zones(header_at_bottom=True).split(elements)
        self.assertTrue(header["is_chapter"])

    def test_page_number_alone_means_chapter_opening(self):
        header, _ = _zones(header_at_bottom=True).split([_element("1", FOOTER_Y)])
        self.assertIsNone(header)

    def test_top_header_is_unchanged_by_default(self):
        top = _element("Chapter 3: Modularity 41", (70, 620, 430, 640))
        header, body = _zones().split([top, _element("Body", BODY_Y)])
        self.assertEqual(header["text"], "Chapter 3: Modularity")
        self.assertEqual(len(body), 1)


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
