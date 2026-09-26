"""Çevrilmiş sayfa belgesi: bloklar, çevrilecek metin birimleri, görseller ve denklemler.
Şema: references/FORMAT.md; dosyaya okunup yazılması translated_pages'tedir.
"""
import copy
from collections import Counter

from page_blocks import Block
from progress import UNKNOWN_CHAPTER

TRANSLATED_FIELDS = ("title", "section", "concepts", "chapter")


class PageDocument:
    """Bir sayfanın belgesi; sardığı sözlük FORMAT.md şemasıdır. Sözlük dışarı açılmaz: işi soran
    modül değil belge yapar, diske yazılacak biçimi as_json verir."""

    def __init__(self, data):
        self._data = data

    def __eq__(self, other):
        return isinstance(other, PageDocument) and self._data == other._data

    def as_json(self):
        """Diske yazılacak sözlüğün kopyası; belge yalnız kendi metotlarıyla değişir."""
        return copy.deepcopy(self._data)

    def number(self):
        return self._data["page"]

    def chapter(self):
        return self._data.get("chapter", dict(UNKNOWN_CHAPTER))

    def concepts(self):
        return self._data.get("concepts", [])

    def toc_entry(self):
        """progress.json'daki içindekiler kaydı: PDF sayfası, bölüm numarası, başlık, kesit."""
        title, section = self._data.get("title", {}), self._data.get("section", {})
        return {"pdf_page": self._data["pdf_page"], "chapter": self._data.get("chapter", {}).get("num"),
                "title_en": title.get("en", ""), "title_tr": title.get("tr", ""),
                "section_en": section.get("en", ""), "section_tr": section.get("tr", "")}

    def translated_fields(self):
        """Yeniden çıkarımın üretmediği, çevirmenin ve kart ajanının yazdığı alanlardan sayfada olanlar."""
        return {field: self._data[field] for field in TRANSLATED_FIELDS if field in self._data}

    def with_concepts(self, cards):
        """Kartları verilen kartlar olan aynı sayfa; bu belge değişmez."""
        return PageDocument({**self._data, "concepts": cards})

    def card_source(self):
        """Kartların yazılacağı sayfa: başlık alanları ile metin bloklarının kart birimleri (content)."""
        content = [unit for unit in (block.card_unit() for block in self.blocks()) if unit]
        return {"id": self._data["id"], "page": self.number(), "chapter": self._data.get("chapter", {}),
                "section": self._data.get("section", {}), "title": self._data.get("title", {}), "content": content}

    def new_terms(self):
        """Çevirmenin sözlüğe önerdiği terimler (glossary_new)."""
        return self._data.get("glossary_new", [])

    def blocks(self):
        return [Block.of(data) for data in self._data["blocks"]]

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

    def image_sources(self):
        return [src for block in self.blocks() for src in block.image_sources()]

    def anchor_texts(self):
        """Blokları görsel yerleştirirken tanıtan İngilizce metinler, blok sırasıyla."""
        return [block.anchor_text() for block in self.blocks()]

    def leading_block_count(self):
        """Sayfanın açıldığı başlık bloklarının sayısı; çapasız görsel bunların altına iner."""
        return next((index for index, block in enumerate(self.blocks()) if not block.leads_page()),
                    len(self._data["blocks"]))

    def insert_image(self, index, src):
        self._data["blocks"].insert(index, {"type": "image", "src": src})

    def display_math(self):
        return [equation for block in self.blocks() for equation in block.equations()]

    def inline_math(self):
        return self._data.get("math", [])


    def media_sources(self):
        """Sayfanın görsel klasörüne kopyalanacak PNG adları."""
        sources = [src for block in self.blocks() for src in block.media_sources()]
        return sources + [item["src"] for item in self.inline_math()]

    def summary(self):
        """Hazırlanan girdinin özeti: sayfa, PDF sayfası, sırayla blok türleri, denklem sayısı."""
        return {"page": self.number(), "pdf_page": self._data["pdf_page"],
                "blocks": self._block_summary(), "math": self._equation_count()}

    def _block_summary(self):
        counts = Counter(block.kind for block in self.blocks())
        return ", ".join(f"{kind}:{count}" for kind, count in counts.items())

    def _equation_count(self):
        return len(self.display_math()) + len(self.inline_math())
