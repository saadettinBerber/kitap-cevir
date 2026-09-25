"""Sayfa belgesindeki blokların türe göre davranışı (references/FORMAT.md → Blok tipleri).

Blok türüne göre dallanma yalnız `Block.of` fabrikasındadır; diğer modüller
polimorfik metotları çağırır. Bloklar JSON sözlüğünü sarar, veri biçimi değişmez.
"""


class Block:
    """Çevrilecek metni olmayan blok; bilinmeyen türler de böyle davranır."""

    def __init__(self, data):
        self.data = data

    @staticmethod
    def of(data):
        return _BLOCK_CLASSES.get(data["type"], Block)(data)

    @property
    def kind(self):
        return self.data["type"]

    def unit_paths(self):
        """(yol eki, {en, tr} birimi) çiftleri; yol eki bloğun kendi yoluna eklenir."""
        return []

    def units(self):
        return [unit for _, unit in self.unit_paths()]

    def fill(self, filler, path):
        for suffix, unit in self.unit_paths():
            filler.fill_unit(unit, path + suffix)

    def card_unit(self):
        """Kart agent'ının okuyacağı tek {type, en, tr} birimi; metni yoksa boş."""
        if not self.units():
            return {}
        return {"type": self.kind, "en": self._joined("en"), "tr": self._joined("tr")}

    def _joined(self, lang):
        """Birimlerin o dildeki metinleri tek metin olur."""
        return " ".join(unit.get(lang, "") for unit in self.units())

    def anchor_text(self):
        """Görsel yerleştirirken bloğu tanıtan İngilizce metin."""
        return self.data.get("en") or ""

    def media_sources(self):
        return []

    def image_sources(self):
        return []

    def equations(self):
        """Ayrı satır denklemleri (LaTeX taşıyan {src, text, latex} sözlükleri)."""
        return []

    def leads_page(self):
        """Sayfa başı görseli bu bloğun altına iner."""
        return False

    def accept(self, visitor):
        """VISITOR: türe göre çıktı (ör. EPUB) ziyaretçide yazılır, dallanma Block.of'ta kalır."""
        return visitor.visit_unknown(self)


class TextBlock(Block):
    """caption, footnote: bloğun kendisi tek bir {en, tr} birimidir."""

    def unit_paths(self):
        return [("", self.data)]

    def accept(self, visitor):
        return visitor.visit_text_unit(self)


class HeadingBlock(TextBlock):
    def leads_page(self):
        return True

    def accept(self, visitor):
        return visitor.visit_heading(self)


class ChapterBlock(HeadingBlock):
    def accept(self, visitor):
        return visitor.visit_chapter(self)


class ParaBlock(Block):
    def unit_paths(self):
        return [(f".sentences[{index}]", sentence) for index, sentence in enumerate(self.data["sentences"])]

    def fill(self, filler, path):
        self.data["sentences"] = filler.fill_sentences(self.data["sentences"], path)

    def anchor_text(self):
        return self._joined("en")

    def accept(self, visitor):
        return visitor.visit_para(self)


class ListBlock(Block):
    def unit_paths(self):
        return [(f".items[{index}]", item) for index, item in enumerate(self.data["items"])]

    def anchor_text(self):
        return self._joined("en")

    def accept(self, visitor):
        return visitor.visit_list(self)


class TableBlock(Block):
    def unit_paths(self):
        return [(f".rows[{r}][{c}]", cell)
                for r, row in enumerate(self.data["rows"]) for c, cell in enumerate(row)]

    def accept(self, visitor):
        return visitor.visit_table(self)


class CodeBlock(Block):
    """Kod çevrilmez; kart agent'ı onu olduğu gibi okur."""

    def card_unit(self):
        return {"type": "code", "code": self.data["code"]}

    def accept(self, visitor):
        return visitor.visit_code(self)


class MediaBlock(Block):
    """PNG'si sayfanın görsel klasörüne kopyalanan blok."""

    def media_sources(self):
        return [self.data["src"]]


class ImageBlock(MediaBlock):
    def image_sources(self):
        return [self.data["src"]]

    def accept(self, visitor):
        return visitor.visit_image(self)


class MathBlock(MediaBlock):
    def equations(self):
        return [self.data]

    def accept(self, visitor):
        return visitor.visit_math(self)


_BLOCK_CLASSES = {
    "caption": TextBlock, "footnote": TextBlock,
    "chapter": ChapterBlock, "heading": HeadingBlock,
    "para": ParaBlock, "list": ListBlock, "table": TableBlock,
    "code": CodeBlock, "image": ImageBlock, "math": MathBlock,
}
