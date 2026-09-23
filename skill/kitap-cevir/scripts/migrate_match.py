"""Eski çevrilmiş sayfadaki en→tr eşleşmelerini yeni çıkarım yapısına taşır.

Eski sayfanın tüm metin birimleri (cümle, başlık, caption, dipnot, liste
maddesi, tablo hücresi) sıralı bir listeye düzleştirilir. Yeni birim için
önce birebir, sonra normalize eşleşme; yeni cümle eski birimlerin birleşimine
ya da eski birim yeni cümlelerin birleşimine eşitse birleştirilerek taşınır.
Eşleşmeyen birimler `pending` listesine düşer (küçük bir çeviri geçişi için).
"""
import re

from extraction.text_utils import clean_ligatures, normalize_spaces
from page_blocks import Block
from page_document import PageDocument

MAX_JOIN = 4
NUMERIC_CELL = re.compile(r"^(?:[\d.,%~+\-–\s]|<br>)*$")
PLACEHOLDER = re.compile(r"⟦eq-\d+⟧")
_TAGS = re.compile(r"<[^>]+>")


class Translations:
    """Eski birimlerden kurulan arama tabloları: tek birim ve ardışık birleşimler."""

    def __init__(self, units):
        self.single = {}
        self.joined = {}
        for index, unit in enumerate(units):
            self.single.setdefault(self.key(unit["en"]), unit["tr"])
            for window in self._windows(units, index):
                self.joined.setdefault(self.key(" ".join(u["en"] for u in window)),
                                       " ".join(u["tr"] for u in window))

    @staticmethod
    def _windows(units, start):
        """start'tan başlayan, 2..MAX_JOIN uzunluğundaki ardışık birim grupları."""
        return [units[start:start + count] for count in range(2, MAX_JOIN + 1) if start + count <= len(units)]

    @classmethod
    def of_page(cls, old_page, fixes):
        """Eski sayfanın çevrilmiş birimleri, sayfa sırasıyla. Yeni çıkarımın metin
        onarımları ('3.14 × 10' → '3.14 × 10^23') eski birimlere de uygulanır ki
        iki taraf aynı biçimde eşleşsin."""
        units = [{"en": u.get("en", ""), "tr": u.get("tr", "")}
                 for u in PageDocument(old_page).text_units() if u.get("en")]
        for unit in units:
            for wrong, right in fixes.items():
                unit["en"] = unit["en"].replace(wrong, right)
                unit["tr"] = unit["tr"].replace(wrong, right)
        return cls(units)

    @staticmethod
    def key(text):
        """Eşleşme anahtarı: ligatür, etiket, yer tutucu, tırnak ve büyük harf farkı yok sayılır."""
        text = PLACEHOLDER.sub(" ", _TAGS.sub(" ", clean_ligatures(text or "")))
        return normalize_spaces(text.replace("`", "").replace("’", "'").replace("“", '"')
                                .replace("”", '"')).lower().strip(" .")

    def lookup(self, text):
        key = self.key(text)
        if not key:
            return ""
        return self.single.get(key) or self.joined.get(key) or ""

    def lookup_single(self, text):
        return self.single.get(self.key(text), "")


class TranslationFiller:
    """Yeni birimlere eski çevirileri yazar; bulunamayanlar `pending`'e düşer."""

    def __init__(self, translations):
        self.translations = translations
        self.pending = []

    def fill_block(self, block, path):
        Block.of(block).fill(self, path)

    def fill_unit(self, unit, path):
        """Birime tr yazar; bulunamazsa ya da yer tutucu eksikse pending'e ekler."""
        if not (unit["en"] or "").strip():
            unit["tr"] = ""
            return True
        translation = self.translations.lookup(unit["en"])
        if not translation and NUMERIC_CELL.match(unit["en"]):
            translation = unit["en"]
        if translation and not self._drops_placeholder(unit, translation):
            unit["tr"] = translation
            return True
        unit["tr"] = ""
        self.pending.append({"path": path, "en": unit["en"], "tr_hint": translation})
        return False

    @staticmethod
    def _drops_placeholder(unit, translation):
        return bool(PLACEHOLDER.search(unit["en"])) and not PLACEHOLDER.search(translation)

    def fill_sentences(self, sentences, path):
        """Ardışık yeni cümlelerin birleşimi eski bir birime eşitse tek cümle olur."""
        merged, index = [], 0
        while index < len(sentences):
            unit, taken = self._merge_run(sentences, index)
            self.fill_unit(unit, f"{path}.sentences[{len(merged)}]")
            merged.append(unit)
            index += taken
        return merged

    def _merge_run(self, sentences, index):
        if self.translations.lookup(sentences[index]["en"]):
            return sentences[index], 1
        for count in range(MAX_JOIN, 1, -1):
            window = sentences[index:index + count]
            joined = " ".join(s["en"] for s in window)
            if len(window) == count and self.translations.lookup_single(joined):
                return {**sentences[index], "en": joined}, count
        return sentences[index], 1
