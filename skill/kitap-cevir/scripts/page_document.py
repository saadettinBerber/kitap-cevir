"""Çevrilmiş sayfa belgesi: bloklar, çevrilecek metin birimleri, görseller ve denklemler.
Şema: references/FORMAT.md; dosyaya okunup yazılması translated_pages'tedir.
"""
from collections import Counter

from page_blocks import Block
from progress import UNKNOWN_CHAPTER


class PageDocument:
    """Bir sayfanın belgesi; `data` sözlüğü FORMAT.md şemasıdır."""

    def __init__(self, data):
        self.data = data

    def number(self):
        return self.data["page"]

    def chapter(self):
        return self.data.get("chapter", dict(UNKNOWN_CHAPTER))

    def concepts(self):
        return self.data.get("concepts", [])

    def blocks(self):
        return [Block.of(data) for data in self.data["blocks"]]

    def text_units(self):
        return [unit for block in self.blocks() for unit in block.units()]

    def missing_translations(self):
        return sum(1 for unit in self.text_units() if unit.get("en") and not unit.get("tr"))

    def is_blank(self):
        """Yalnız görsel içeren sayfa (bölüm sonu boşluğu) çevrilecek bir şey taşımaz."""
        return all(block.image_sources() for block in self.blocks())

    def display_math(self):
        return [equation for block in self.blocks() for equation in block.equations()]

    def inline_math(self):
        return self.data.get("math", [])

    def equation_count(self):
        return len(self.display_math()) + len(self.inline_math())

    def media_sources(self):
        """Sayfanın görsel klasörüne kopyalanacak PNG adları."""
        sources = [src for block in self.blocks() for src in block.media_sources()]
        return sources + [item["src"] for item in self.inline_math()]

    def block_summary(self):
        counts = Counter(block.kind for block in self.blocks())
        return ", ".join(f"{kind}:{count}" for kind, count in counts.items())
