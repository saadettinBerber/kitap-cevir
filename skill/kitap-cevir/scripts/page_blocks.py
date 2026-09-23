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
        units = self.units()
        if not units:
            return {}
        return {"type": self.kind, "en": " ".join(unit.get("en", "") for unit in units),
                "tr": " ".join(unit.get("tr", "") for unit in units)}

    def anchor_text(self):
        """Görsel yerleştirirken bloğu tanıtan İngilizce metin."""
        return self.data.get("en") or self.data.get("html") or ""

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


class TextBlock(Block):
    """caption, footnote: bloğun kendisi tek bir {en, tr} birimidir."""

    def unit_paths(self):
        return [("", self.data)]


class HeadingBlock(TextBlock):
    """chapter, heading."""

    def leads_page(self):
        return True


class HtmlBlock(Block):
    def leads_page(self):
        return True


class ParaBlock(Block):
    def unit_paths(self):
        return [(f".sentences[{index}]", sentence) for index, sentence in enumerate(self.data["sentences"])]

    def fill(self, filler, path):
        self.data["sentences"] = filler.fill_sentences(self.data["sentences"], path)

    def anchor_text(self):
        return " ".join(unit.get("en", "") for unit in self.units())


class ListBlock(Block):
    def unit_paths(self):
        return [(f".items[{index}]", item) for index, item in enumerate(self.data["items"])]

    def anchor_text(self):
        return " ".join(unit.get("en", "") for unit in self.units())


class TableBlock(Block):
    def unit_paths(self):
        return [(f".rows[{r}][{c}]", cell)
                for r, row in enumerate(self.data["rows"]) for c, cell in enumerate(row)]


class CodeBlock(Block):
    """Kod çevrilmez; kart agent'ı onu olduğu gibi okur."""

    def card_unit(self):
        return {"type": "code", "code": self.data["code"]}


class MediaBlock(Block):
    """PNG'si sayfanın görsel klasörüne kopyalanan blok."""

    def media_sources(self):
        return [self.data["src"]]


class ImageBlock(MediaBlock):
    def image_sources(self):
        return [self.data["src"]]


class MathBlock(MediaBlock):
    def equations(self):
        return [self.data]


_BLOCK_CLASSES = {
    "caption": TextBlock, "footnote": TextBlock,
    "chapter": HeadingBlock, "heading": HeadingBlock,
    "html": HtmlBlock, "para": ParaBlock, "list": ListBlock, "table": TableBlock,
    "code": CodeBlock, "image": ImageBlock, "math": MathBlock,
}
