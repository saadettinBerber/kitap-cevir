"""Çevrilmiş sayfa belgesi: bloklar, çevrilecek metin birimleri, görseller ve denklemler.
Şema: references/FORMAT.md; dosyaya okunup yazılması translated_pages'tedir.
"""
import copy
from collections import Counter

from page_blocks import Block
from progress import UNKNOWN_CHAPTER

CARRIED_FIELDS = ("title", "section", "concepts")


class PageDocument:
    """Bir sayfanın belgesi; sardığı sözlük FORMAT.md şemasıdır. Sözlüğü okuyup karar veren iş belgenin
    metodudur, soran modülün değil. Sözlük kopyalanmadan sarılır: taşıma onu yerinde doldurur."""

    def __init__(self, data):
        self._data = data

    def __eq__(self, other):
        return isinstance(other, PageDocument) and self._data == other._data

    def as_json(self):
        """Diske yazılacak sözlüğün kopyası; kopyayı değiştirmek belgeyi değiştirmez."""
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

    def take_translation_of(self, old, source):
        """Taşıma: yeniden çıkarılmış bu sayfa, eski sayfanın (old) çevirmen ve kart ajanınca yazılmış
        kısımlarını alır. Birimlerin eski çevirisini kaynak (TranslationSource) söyler."""
        for block in self.blocks():
            block.fill(source)
        self._take_fields_of(old)
        self._take_chapter_of(old)
        self._take_latex_of(old)

    def _take_fields_of(self, old):
        """Başlık, kesit ve kartlar eski sayfadan gelir. Eski sayfanın terimleri sözlükte olduğundan
        yeni terim listesi boşalır."""
        for field in CARRIED_FIELDS:
            self._data[field] = old._data.get(field, self._data.get(field))
        self._data["glossary_new"] = []

    def _take_chapter_of(self, old):
        """Bölüm yalnız Türkçesi yoksa eski sayfadan gelir."""
        if not self._data.get("chapter", {}).get("tr"):
            self._data["chapter"] = old._data.get("chapter", self._data["chapter"])

    def _take_latex_of(self, old):
        """Eski sayfada aynı PNG için yazılmış LaTeX gelir; ayrı satır denkleminin LaTeX'i satır
        içindekinden önceliklidir."""
        known = {item["src"]: item.get("latex", "") for item in old.inline_math() + old.display_math()}
        for item in self.display_math() + self.inline_math():
            item["latex"] = item.get("latex") or known.get(item["src"], "")

    def missing_latex(self):
        """LaTeX'i olmayan denklemler: {path, src}; önce ayrı satır denklemleri, sonra satır içindekiler."""
        display = [{"path": f"blocks[{index}]", "src": equation["src"]} for index, block in enumerate(self.blocks())
                   for equation in block.equations() if not equation["latex"]]
        return display + [{"path": f"math[{index}]", "src": item["src"]}
                          for index, item in enumerate(self.inline_math()) if not item["latex"]]

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
