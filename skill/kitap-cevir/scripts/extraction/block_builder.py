"""Düzen öğelerini (LayoutElement) references/FORMAT.md blok şemasına (yalnız `en` tarafı) çevirir:
başlık seviyesi, bölüm açılışı, caption türleri, dipnot, paragraf üslubu, liste,
tablo, görsel. Eşikler ve desenler progress.json -> extraction ayarlarındadır.
"""
import re

from extraction.text_utils import is_numeric_only, split_sentences, strip_list_marker

MAX_HEADING_CHARS = 100
_CHAPTER_AUTHOR = re.compile(r"^(?:by|with) [A-Z]")
_BIBLIOGRAPHY_ENTRY = re.compile(r"^\[[A-Za-z0-9]+\]:")
_LIST_MARKER = re.compile(r"^(\d+[.)])\s")


class TypeScale:
    """Başlığı puntosu ele verir: bölüm numarası, bölüm başlığı, kesit ve alt kesit
    eşikleri (progress.json -> extraction)."""

    def __init__(self, settings):
        self.chapter_number = settings["chapter_number_min_size"]
        self.chapter_title = settings["chapter_title_min_size"]
        self.section = settings["section_min_size"]
        self.subsection = settings["subsection_min_size"]

    def reads_as_heading(self, element):
        """Okuyucunun türü değil punto karar verir. Liste maddesine gömülmüş
        öğelerin tipini ODL düzleştirir (hepsi paragraf olur): alt başlık puntosu
        yeter. Okuyucu bölüm başlığını paragraf sanabilir (LiteParse): bölüm başlığı
        puntosu yeter. Uzun ya da noktalamayla biten metin yine paragraf kalır."""
        if element.is_nested:
            return element.font_size >= self.subsection
        return element.font_size >= self.chapter_title

    def is_chapter_number(self, size):
        return size >= self.chapter_number

    def is_chapter_title(self, size):
        return size >= self.chapter_title

    def heading_level(self, size):
        if size >= self.section:
            return 1
        return 2 if size >= self.subsection else 3


class SpecialParagraphs:
    """Paragraf görünümlü ama başka türde blok: caption, dipnot, kalın küçük başlık."""

    def __init__(self, settings, fixer):
        self.table_caption = re.compile(settings["table_caption_pattern"])
        self.equation_caption = re.compile(settings["equation_caption_pattern"])
        self.footnote_max_size = settings["footnote_max_size"]
        self.bold_heading_font = settings["bold_heading_font"]
        self.fixer = fixer

    def blocks_of(self, element, text):
        """Özel bir tür değilse boş liste."""
        if self.table_caption.match(text):
            return [{"type": "caption", "kind": "table", "en": self.fixer.rich(text)}]
        if self.equation_caption.match(text):
            return [{"type": "caption", "kind": "equation", "en": self.fixer.rich(text)}]
        if element.font_size <= self.footnote_max_size:
            return [{"type": "footnote", "en": self.fixer.rich(text)}]
        if self._is_bold_heading(element.font):
            return [{"type": "heading", "level": 3, "en": text}]
        return []

    def _is_bold_heading(self, font):
        return self.bold_heading_font in font and "bold" in font.lower()


class BlockBuilder:
    """Bir sayfanın düzen öğelerini bloklara çevirir; metni sayfanın TextFixer'ı onarır."""

    def __init__(self, settings, fixer):
        self.fixer = fixer
        self.scale = TypeScale(settings)
        self.special = SpecialParagraphs(settings, fixer)
        self.listing_caption = re.compile(settings["listing_caption_pattern"])
        label = settings["chapter_label_pattern"]
        self.chapter_label = re.compile(label) if label else None
        self._builders = {"list item": self._list_item_blocks, "heading": self._heading_blocks,
                          "paragraph": self._paragraph_blocks, "list": self._list_blocks,
                          "image": self._image_blocks, "caption": self._caption_blocks,
                          "table": self._table_blocks}

    def blocks_of(self, element):
        label = self._chapter_label_blocks(element)
        if label:
            return label
        kind = element.kind
        if kind == "paragraph" and self.scale.reads_as_heading(element):
            kind = "heading"
        build = self._builders.get(kind)
        return build(element) if build else []

    def _plain(self, element):
        return self.fixer.plain(element.text)

    def _chapter_label_blocks(self, element):
        """Bölüm etiketi satırı (CHAPTER 7 gibi); ODL kimi kitapta bunu paragraf
        sanar, ChapterOpener numarayı bölüm başlığına taşır."""
        match = self.chapter_label.match(self._plain(element)) if self.chapter_label else None
        return [{"type": "chapter_number", "num": int(match.group(1))}] if match else []

    def _heading_blocks(self, element):
        text, size = self._plain(element), element.font_size
        if not text:
            return []
        if self._looks_like_paragraph(text):
            return self._paragraph_blocks(element)
        if self.scale.is_chapter_number(size) and text.isdigit():
            return [{"type": "chapter_number", "num": int(text)}]
        if self.scale.is_chapter_title(size):
            return [{"type": "chapter", "en": text}]
        if self.listing_caption.match(text):
            return [{"type": "caption", "kind": "listing", "en": text}]
        return [{"type": "heading", "level": self.scale.heading_level(size), "en": text}]

    @staticmethod
    def _looks_like_paragraph(text):
        """ODL karışık fontlu (satır içi kod/denklem) gövde satırını başlık sanabilir;
        uzun ya da noktalamayla biten 'başlık' gövde metnidir."""
        return len(text) > MAX_HEADING_CHARS or text.endswith((".", ":", ";", ","))

    def _paragraph_blocks(self, element):
        text = self._plain(element)
        if not text or is_numeric_only(text):
            return []
        special = self.special.blocks_of(element, text)
        if special:
            return special
        block = {"type": "para", "sentences": self._sentences(self.fixer.rich(text))}
        style = self._paragraph_style(text, element.font)
        if style:
            block["style"] = style
        return [block] if block["sentences"] else []

    @staticmethod
    def _sentences(text):
        return [{"en": sentence} for sentence in split_sentences(text) if not is_numeric_only(sentence)]

    @staticmethod
    def _paragraph_style(text, font):
        if _BIBLIOGRAPHY_ENTRY.match(text):
            return "reference"
        return "quote" if "Italic" in font else ""

    def _list_item_blocks(self, element):
        """Liste maddesi paragrafa dönüşürken numarası korunur ('2. If the shop
        offers...'): numara tek başına cümle sayılıp düşerse madde, altındaki
        açıklama paragrafıyla eşleşemez."""
        blocks = self._paragraph_blocks(element)
        marker = _LIST_MARKER.match(self._plain(element))
        if marker and blocks and blocks[0]["type"] == "para":
            first = blocks[0]["sentences"][0]
            first["en"] = f"{marker.group(1)} {first['en']}"
        return blocks

    def _list_blocks(self, element):
        items = [{"en": strip_list_marker(self._rich(item.text))} for item in element.list_items]
        return [{"type": "list", "ordered": element.is_ordered, "items": items}]

    def _table_blocks(self, element):
        rows = [[{"en": self._rich(text)} for text in row] for row in element.table_rows]
        return [{"type": "table", "rows": rows}] if rows else []

    def _caption_blocks(self, element):
        return [{"type": "caption", "en": self._rich(element.text)}]

    @staticmethod
    def _image_blocks(element):
        return [{"type": "image", "src": element.image_file}]

    def _rich(self, text):
        return self.fixer.rich(self.fixer.plain(text))


class ChapterOpener:
    """Bölüm açılışı düzen okuyucusunda ayrı öğeler olarak gelir: chapter_number + chapter +
    'by ...' paragrafı. Bunlar tek chapter bloğunda birleşir."""

    def __init__(self, blocks):
        self.blocks = blocks

    def merged(self):
        merged, pending_number = [], None
        for block in self.blocks:
            if block["type"] == "chapter_number":
                pending_number = block["num"]
            elif block["type"] == "chapter":
                block["num"] = pending_number
                merged.append(block)
            elif merged and merged[-1]["type"] == "chapter" and self._author_line(block):
                merged[-1]["author"] = self._author_line(block)
            else:
                merged.append(block)
        return merged

    @staticmethod
    def _author_line(block):
        if block.get("type") != "para" or len(block["sentences"]) != 1:
            return ""
        text = block["sentences"][0]["en"]
        return text if _CHAPTER_AUTHOR.match(text) else ""
