"""Düzen öğelerini (LayoutElement) references/FORMAT.md blok şemasına (yalnız `en` tarafı) çevirir:
başlık seviyesi, bölüm açılışı, caption türleri, dipnot, paragraf üslubu, liste,
tablo, görsel. Eşikler ve desenler progress.json -> extraction ayarlarındadır.
"""
import re

from extraction.settings import optional_pattern
from extraction.text_utils import is_numeric_only, split_sentences, strip_list_marker

MAX_HEADING_CHARS = 100
SECTION_LEVEL, SUBSECTION_LEVEL, MINOR_HEADING_LEVEL = 1, 2, 3
_BODY_TEXT_ENDINGS = (".", ":", ";", ",")
_BIBLIOGRAPHY_ENTRY = re.compile(r"^\[[A-Za-z0-9]+\]:")
_LIST_MARKER = re.compile(r"^(\d+[.)])\s")


def _looks_like_paragraph(text):
    """ODL karışık fontlu (satır içi kod/denklem) gövde satırını başlık sanabilir;
    uzun ya da noktalamayla biten 'başlık' gövde metnidir."""
    return len(text) > MAX_HEADING_CHARS or text.endswith(_BODY_TEXT_ENDINGS)


def _paragraph_style(text, font):
    if _BIBLIOGRAPHY_ENTRY.match(text):
        return "reference"
    return "quote" if "Italic" in font else ""


class Headings:
    """Başlığı puntosu ele verir: bölüm numarası, bölüm başlığı, kesit ve alt kesit
    eşikleri ile listing caption deseni (progress.json -> extraction)."""

    def __init__(self, settings):
        self._chapter_number = settings["chapter_number_min_size"]
        self._chapter_title = settings["chapter_title_min_size"]
        self._section = settings["section_min_size"]
        self._subsection = settings["subsection_min_size"]
        self._listing_caption = re.compile(settings["listing_caption_pattern"])

    def reads_as_heading(self, element, text):
        """Uzun ya da noktalamayla biten metin, türü ya da puntosu ne derse desin paragraftır."""
        return self._has_heading_kind_or_size(element) and not _looks_like_paragraph(text)

    def _has_heading_kind_or_size(self, element):
        """Paragrafta okuyucunun türü değil punto karar verir. Liste maddesine gömülmüş
        öğelerin tipini ODL düzleştirir (hepsi paragraf olur): alt başlık puntosu
        yeter. Okuyucu bölüm başlığını paragraf sanabilir (LiteParse): bölüm başlığı
        puntosu yeter."""
        if element.kind != "paragraph":
            return element.kind == "heading"
        return element.font_size >= (self._subsection if element.is_nested else self._chapter_title)

    def block_of(self, text, size):
        """Başlık türü punto ve desenden: bölüm numarası, bölüm başlığı, listing caption, kesit."""
        if size >= self._chapter_number and text.isdigit():
            return {"type": "chapter_number", "num": int(text)}
        if size >= self._chapter_title:
            return {"type": "chapter", "en": text}
        if self._listing_caption.match(text):
            return {"type": "caption", "kind": "listing", "en": text}
        return {"type": "heading", "level": self._level(size), "en": text}

    def _level(self, size):
        if size >= self._section:
            return SECTION_LEVEL
        return SUBSECTION_LEVEL if size >= self._subsection else MINOR_HEADING_LEVEL


class Paragraphs:
    """Paragraf öğesinin blokları: paragraf görünümlü özel türler (caption, dipnot, kalın
    küçük başlık) ya da üslubuyla (kaynakça, alıntı) cümlelerine bölünmüş paragraf."""

    def __init__(self, settings, fixer):
        self._table_caption = re.compile(settings["table_caption_pattern"])
        self._equation_caption = re.compile(settings["equation_caption_pattern"])
        self._footnote_max_size = settings["footnote_max_size"]
        self._bold_heading_font = settings["bold_heading_font"]
        self._fixer = fixer

    def blocks_of(self, element):
        """Yalnız sayıdan oluşan metin (sayfa numarası gibi) blok vermez."""
        text = self._fixer.plain(element.text)
        if not text or is_numeric_only(text):
            return []
        return self._special_blocks(element, text) or self._para_blocks(element, text)

    def _special_blocks(self, element, text):
        """Özel bir tür değilse boş liste."""
        if self._table_caption.match(text):
            return [{"type": "caption", "kind": "table", "en": self._fixer.rich(element.text)}]
        if self._equation_caption.match(text):
            return [{"type": "caption", "kind": "equation", "en": self._fixer.rich(element.text)}]
        if element.font_size <= self._footnote_max_size:
            return [{"type": "footnote", "en": self._fixer.rich(element.text)}]
        if self._is_bold_heading(element.font):
            return [{"type": "heading", "level": MINOR_HEADING_LEVEL, "en": text}]
        return []

    def _is_bold_heading(self, font):
        return self._bold_heading_font in font and "bold" in font.lower()

    def _para_blocks(self, element, text):
        block = {"type": "para", "sentences": self._sentences(element.text)}
        style = _paragraph_style(text, element.font)
        if style:
            block["style"] = style
        return [block] if block["sentences"] else []

    def _sentences(self, raw):
        sentences = split_sentences(self._fixer.rich(raw))
        return [{"en": sentence} for sentence in sentences if not is_numeric_only(sentence)]


class BlockBuilder:
    """Bir sayfanın düzen öğelerini bloklara çevirir; metni sayfanın TextFixer'ı onarır."""

    def __init__(self, settings, fixer):
        self._fixer = fixer
        self._headings = Headings(settings)
        self._paragraphs = Paragraphs(settings, fixer)
        self._chapter_label = optional_pattern(settings["chapter_label_pattern"])
        self._builders = {"chapter label": self._chapter_label_blocks,
                          "list item": self._list_item_blocks, "heading": self._heading_blocks,
                          "paragraph": self._paragraphs.blocks_of, "list": self._list_blocks,
                          "image": self._image_blocks, "caption": self._caption_blocks,
                          "table": self._table_blocks}

    def blocks_of(self, element):
        build = self._builders.get(self._kind_of(element))
        return build(element) if build else []

    def _kind_of(self, element):
        """Okuyucunun verdiği tür düzeltilir: bölüm etiketi satırı, puntosu başlık
        olan paragraf ve gövde metni gibi okunan başlık."""
        text = self._plain(element)
        if self._chapter_label.match(text):
            return "chapter label"
        if self._headings.reads_as_heading(element, text):
            return "heading"
        return "paragraph" if element.kind == "heading" else element.kind

    def _plain(self, element):
        return self._fixer.plain(element.text)

    def _chapter_label_blocks(self, element):
        """Bölüm etiketi satırı (CHAPTER 7 gibi); ODL kimi kitapta bunu paragraf
        sanar, ChapterOpener numarayı bölüm başlığına taşır."""
        match = self._chapter_label.match(self._plain(element))
        return [{"type": "chapter_number", "num": int(match.group(1))}]

    def _heading_blocks(self, element):
        text = self._plain(element)
        return [self._headings.block_of(text, element.font_size)] if text else []

    def _list_item_blocks(self, element):
        """Liste maddesi paragrafa dönüşürken numarası korunur ('2. If the shop
        offers...'): numara tek başına cümle sayılıp düşerse madde, altındaki
        açıklama paragrafıyla eşleşemez."""
        blocks = self._paragraphs.blocks_of(element)
        marker = _LIST_MARKER.match(self._plain(element))
        if marker and blocks and blocks[0]["type"] == "para":
            first = blocks[0]["sentences"][0]
            first["en"] = f"{marker.group(1)} {first['en']}"
        return blocks

    def _list_blocks(self, element):
        items = [{"en": strip_list_marker(self._fixer.rich(item.text))} for item in element.list_items]
        return [{"type": "list", "ordered": element.is_ordered, "items": items}]

    def _table_blocks(self, element):
        rows = [[{"en": self._fixer.rich(text)} for text in row] for row in element.table_rows]
        return [{"type": "table", "rows": rows}] if rows else []

    def _caption_blocks(self, element):
        return [{"type": "caption", "en": self._fixer.rich(element.text)}]

    @staticmethod
    def _image_blocks(element):
        return [{"type": "image", "src": element.image_file}]
