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


class BlockBuilder:
    """Bir sayfanın düzen öğelerini bloklara çevirir; metni sayfanın TextFixer'ı onarır."""

    def __init__(self, settings, fixer):
        self.settings = settings
        self.fixer = fixer
        self.listing_caption = re.compile(settings["listing_caption_pattern"])
        self.table_caption = re.compile(settings["table_caption_pattern"])
        self.equation_caption = re.compile(settings["equation_caption_pattern"])
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
        if kind == "paragraph" and self._reads_as_heading(element):
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

    def _reads_as_heading(self, element):
        """Başlığı puntosu ele verir, okuyucunun türü değil. Liste maddesine gömülmüş
        öğelerin tipini ODL düzleştirir (hepsi paragraf olur): alt başlık puntosu
        yeter. Okuyucu bölüm başlığını paragraf sanabilir (LiteParse): bölüm başlığı
        puntosu yeter. Uzun ya da noktalamayla biten metin yine paragraf kalır."""
        size = element.font_size
        if element.is_nested:
            return size >= self.settings["subsection_min_size"]
        return size >= self.settings["chapter_title_min_size"]

    def _heading_blocks(self, element):
        text, size = self._plain(element), element.font_size
        if not text:
            return []
        if self._looks_like_paragraph(text):
            return self._paragraph_blocks(element)
        if size >= self.settings["chapter_number_min_size"] and text.isdigit():
            return [{"type": "chapter_number", "num": int(text)}]
        if size >= self.settings["chapter_title_min_size"]:
            return [{"type": "chapter", "en": text}]
        if self.listing_caption.match(text):
            return [{"type": "caption", "kind": "listing", "en": text}]
        return [{"type": "heading", "level": self._heading_level(size), "en": text}]

    @staticmethod
    def _looks_like_paragraph(text):
        """ODL karışık fontlu (satır içi kod/denklem) gövde satırını başlık sanabilir;
        uzun ya da noktalamayla biten 'başlık' gövde metnidir."""
        return len(text) > MAX_HEADING_CHARS or text.endswith((".", ":", ";", ","))

    def _heading_level(self, size):
        if size >= self.settings["section_min_size"]:
            return 1
        return 2 if size >= self.settings["subsection_min_size"] else 3

    def _paragraph_blocks(self, element):
        text = self._plain(element)
        if not text or is_numeric_only(text):
            return []
        special = self._special_paragraph(element, text)
        if special:
            return special
        block = {"type": "para", "sentences": self._sentences(self.fixer.rich(text))}
        style = self._paragraph_style(text, element.font)
        if style:
            block["style"] = style
        return [block] if block["sentences"] else []

    def _special_paragraph(self, element, text):
        """Paragraf görünümlü ama başka türde blok: caption, dipnot, kalın küçük başlık."""
        if self.table_caption.match(text):
            return [{"type": "caption", "kind": "table", "en": self.fixer.rich(text)}]
        if self.equation_caption.match(text):
            return [{"type": "caption", "kind": "equation", "en": self.fixer.rich(text)}]
        if element.font_size <= self.settings["footnote_max_size"]:
            return [{"type": "footnote", "en": self.fixer.rich(text)}]
        if self._is_bold_heading(element.font):
            return [{"type": "heading", "level": 3, "en": text}]
        return []

    def _is_bold_heading(self, font):
        return self.settings["bold_heading_font"] in font and "bold" in font.lower()

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
