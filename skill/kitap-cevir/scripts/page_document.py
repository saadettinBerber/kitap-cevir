"""Çevrilmiş sayfa belgesi: bloklar, çevrilecek metin birimleri, görseller ve denklemler.
Şema: references/FORMAT.md; dosyaya okunup yazılması translated_pages'tedir.
"""
import copy
from collections import Counter

from page_blocks import Block
from progress import UNKNOWN_CHAPTER


class PageDocument:
    """Bir sayfanın belgesi; `data` sözlüğü FORMAT.md şemasıdır."""

    def __init__(self, data):
        self.data = data

    def as_json(self):
        """Diske yazılacak sözlüğün kopyası; belge yalnız kendi metotlarıyla değişir."""
        return copy.deepcopy(self.data)

    def number(self):
        return self.data["page"]

    def chapter(self):
        return self.data.get("chapter", dict(UNKNOWN_CHAPTER))

    def concepts(self):
        return self.data.get("concepts", [])

    def card_source(self):
        """Kartların yazılacağı sayfa: başlık alanları ile metin bloklarının kart birimleri (content)."""
        content = [unit for unit in (block.card_unit() for block in self.blocks()) if unit]
        return {"id": self.data["id"], "page": self.number(), "chapter": self.data.get("chapter", {}),
                "section": self.data.get("section", {}), "title": self.data.get("title", {}), "content": content}

    def blocks(self):
        return [Block.of(data) for data in self.data["blocks"]]

    def text_units(self):
        return [unit for block in self.blocks() for unit in block.units()]

    def unit_paths(self):
        """(yol, birim) çiftleri; yol sayfa kökünden yazılır: 'blocks[3].sentences[1]'."""
        return [(f"blocks[{index}]{suffix}", unit)
                for index, block in enumerate(self.blocks()) for suffix, unit in block.unit_paths()]

    def fill_translations(self, filler):
        """Her blok birimlerine eski çevirileri yazar (taşıma)."""
        for block in self.blocks():
            block.fill(filler)

    def missing_translations(self):
        return sum(1 for unit in self.text_units() if unit.get("en") and not unit.get("tr"))

    def is_blank(self):
        """Yalnız görsel içeren sayfa (bölüm sonu boşluğu) çevrilecek bir şey taşımaz."""
        return all(block.image_sources() for block in self.blocks())

    def display_math(self):
        return [equation for block in self.blocks() for equation in block.equations()]

    def inline_math(self):
        return self.data.get("math", [])


    def media_sources(self):
        """Sayfanın görsel klasörüne kopyalanacak PNG adları."""
        sources = [src for block in self.blocks() for src in block.media_sources()]
        return sources + [item["src"] for item in self.inline_math()]

    def summary(self):
        """Hazırlanan girdinin özeti: sayfa, PDF sayfası, sırayla blok türleri, denklem sayısı."""
        return {"page": self.number(), "pdf_page": self.data["pdf_page"],
                "blocks": self._block_summary(), "math": self._equation_count()}

    def _block_summary(self):
        counts = Counter(block.kind for block in self.blocks())
        return ", ".join(f"{kind}:{count}" for kind, count in counts.items())

    def _equation_count(self):
        return len(self.display_math()) + len(self.inline_math())
