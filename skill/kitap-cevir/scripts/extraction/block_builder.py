"""Düzen öğelerini (LayoutElement) references/FORMAT.md blok şemasına (yalnız `en` tarafı) çevirir:
başlık seviyesi, bölüm açılışı, caption türleri, dipnot, paragraf üslubu, liste,
tablo, görsel. Eşikler ve desenler progress.json -> extraction ayarlarındadır.
"""
import re

from extraction.text_utils import is_numeric_only, split_sentences, strip_list_marker

MAX_HEADING_CHARS = 100
_BIBLIOGRAPHY_ENTRY = re.compile(r"^\[[A-Za-z0-9]+\]:")
_LIST_MARKER = re.compile(r"^(\d+[.)])\s")


def _looks_like_paragraph(text):
    """ODL karışık fontlu (satır içi kod/denklem) gövde satırını başlık sanabilir;
    uzun ya da noktalamayla biten 'başlık' gövde metnidir."""
    return len(text) > MAX_HEADING_CHARS or text.endswith((".", ":", ";", ","))


def _sentences(text):
    return [{"en": sentence} for sentence in split_sentences(text) if not is_numeric_only(sentence)]


def _paragraph_style(text, font):
    if _BIBLIOGRAPHY_ENTRY.match(text):
        return "reference"
    return "quote" if "Italic" in font else ""


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
            return [{"type": "caption", "kind": "table", "en": self.fixer.rich(element.text)}]
        if self.equation_caption.match(text):
            return [{"type": "caption", "kind": "equation", "en": self.fixer.rich(element.text)}]
        if element.font_size <= self.footnote_max_size:
            return [{"type": "footnote", "en": self.fixer.rich(element.text)}]
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
        self._builders = {"chapter label": self._chapter_label_blocks,
                          "list item": self._list_item_blocks, "heading": self._heading_blocks,
                          "paragraph": self._paragraph_blocks, "list": self._list_blocks,
                          "image": self._image_blocks, "caption": self._caption_blocks,
                          "table": self._table_blocks}

    def blocks_of(self, element):
        build = self._builders.get(self._kind_of(element))
        return build(element) if build else []

    def _kind_of(self, element):
        """Okuyucunun verdiği tür düzeltilir: bölüm etiketi satırı, puntosu başlık
        olan paragraf ve gövde metni gibi okunan başlık."""
        text = self._plain(element)
        if self._is_chapter_label(text):
            return "chapter label"
        kind = "heading" if element.kind == "paragraph" and self.scale.reads_as_heading(element) else element.kind
        if kind == "heading" and _looks_like_paragraph(text):
            return "paragraph"
        return kind

    def _plain(self, element):
        return self.fixer.plain(element.text)

    def _is_chapter_label(self, text):
        return bool(self.chapter_label and self.chapter_label.match(text))

    def _chapter_label_blocks(self, element):
        """Bölüm etiketi satırı (CHAPTER 7 gibi); ODL kimi kitapta bunu paragraf
        sanar, ChapterOpener numarayı bölüm başlığına taşır."""
        match = self.chapter_label.match(self._plain(element))
        return [{"type": "chapter_number", "num": int(match.group(1))}]

    def _heading_blocks(self, element):
        text = self._plain(element)
        return [self._heading_block(text, element.font_size)] if text else []

    def _heading_block(self, text, size):
        """Başlık türü punto ve desenden: bölüm numarası, bölüm başlığı, listing caption, kesit."""
        if self.scale.is_chapter_number(size) and text.isdigit():
            return {"type": "chapter_number", "num": int(text)}
        if self.scale.is_chapter_title(size):
            return {"type": "chapter", "en": text}
        if self.listing_caption.match(text):
            return {"type": "caption", "kind": "listing", "en": text}
        return {"type": "heading", "level": self.scale.heading_level(size), "en": text}

    def _paragraph_blocks(self, element):
        text = self._plain(element)
        if not text or is_numeric_only(text):
            return []
        special = self.special.blocks_of(element, text)
        if special:
            return special
        block = {"type": "para", "sentences": _sentences(self.fixer.rich(element.text))}
        style = _paragraph_style(text, element.font)
        if style:
            block["style"] = style
        return [block] if block["sentences"] else []

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
        items = [{"en": strip_list_marker(self.fixer.rich(item.text))} for item in element.list_items]
        return [{"type": "list", "ordered": element.is_ordered, "items": items}]

    def _table_blocks(self, element):
        rows = [[{"en": self.fixer.rich(text)} for text in row] for row in element.table_rows]
        return [{"type": "table", "rows": rows}] if rows else []

    def _caption_blocks(self, element):
        return [{"type": "caption", "en": self.fixer.rich(element.text)}]

    @staticmethod
    def _image_blocks(element):
        return [{"type": "image", "src": element.image_file}]
