"""ODL öğelerini references/FORMAT.md blok şemasına (yalnız `en` tarafı) çevirir:
başlık seviyesi, bölüm açılışı, caption türleri, dipnot, paragraf üslubu, liste,
tablo, görsel. Eşikler ve desenler progress.json -> extraction ayarlarındadır.
"""
import os
import re

from extraction.text_utils import is_numeric_only, split_sentences, strip_list_marker

MAX_HEADING_CHARS = 100
_CHAPTER_AUTHOR = re.compile(r"^(?:by|with) [A-Z]")
_BIBLIOGRAPHY_ENTRY = re.compile(r"^\[[A-Za-z0-9]+\]:")
_LIST_MARKER = re.compile(r"^(\d+[.)])\s")


class BlockBuilder:
    """Bir sayfanın ODL öğelerini bloklara çevirir; metni sayfanın TextFixer'ı onarır."""

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
        kind = element.get("type")
        if kind == "paragraph" and self._is_nested_heading(element):
            kind = "heading"
        build = self._builders.get(kind)
        return build(element) if build else []

    def _plain(self, element):
        return self.fixer.plain(element.get("content"))

    def _chapter_label_blocks(self, element):
        """Bölüm etiketi satırı (CHAPTER 7 gibi); ODL kimi kitapta bunu paragraf
        sanar, ChapterOpener numarayı bölüm başlığına taşır."""
        match = self.chapter_label.match(self._plain(element)) if self.chapter_label else None
        return [{"type": "chapter_number", "num": int(match.group(1))}] if match else []

    def _is_nested_heading(self, element):
        """Liste maddesine gömülmüş öğelerin tipini ODL düzleştirir (hepsi
        paragraf olur); başlık puntosundaki bir öğe aslında başlıktır."""
        return (element.get("nested")
                and (element.get("font size") or 0) >= self.settings["subsection_min_size"])

    def _heading_blocks(self, element):
        text, size = self._plain(element), element.get("font size") or 0
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
        style = self._paragraph_style(text, element.get("font") or "")
        if style:
            block["style"] = style
        return [block] if block["sentences"] else []

    def _special_paragraph(self, element, text):
        """Paragraf görünümlü ama başka türde blok: caption, dipnot, kalın küçük başlık."""
        if self.table_caption.match(text):
            return [{"type": "caption", "kind": "table", "en": self.fixer.rich(text)}]
        if self.equation_caption.match(text):
            return [{"type": "caption", "kind": "equation", "en": self.fixer.rich(text)}]
        if (element.get("font size") or 0) <= self.settings["footnote_max_size"]:
            return [{"type": "footnote", "en": self.fixer.rich(text)}]
        if self._is_bold_heading(element.get("font") or ""):
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
        items = [{"en": strip_list_marker(self._rich(item.get("content")))}
                 for item in element.get("list items", [])]
        ordered = element.get("numbering style", "unordered") != "unordered"
        return [{"type": "list", "ordered": ordered, "items": items}]

    def _table_blocks(self, element):
        rows = [[self._cell(cell) for cell in row.get("cells", [])] for row in element.get("rows", [])]
        return [{"type": "table", "rows": rows}] if rows else []

    def _cell(self, cell):
        return {"en": self._rich(" ".join(kid.get("content", "") for kid in cell.get("kids", [])))}

    def _caption_blocks(self, element):
        return [{"type": "caption", "en": self._rich(element.get("content"))}]

    @staticmethod
    def _image_blocks(element):
        return [{"type": "image", "src": os.path.basename(element.get("source", ""))}]

    def _rich(self, text):
        return self.fixer.rich(self.fixer.plain(text))


class ChapterOpener:
    """Bölüm açılışı ODL'de ayrı öğeler olarak gelir: chapter_number + chapter +
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
