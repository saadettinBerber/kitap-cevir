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
        self._single = self._first_translations(units)
        self._joined = self._first_translations(_joined_windows(units))

    @classmethod
    def of_page(cls, old_page, fixes):
        """Eski sayfanın çevrilmiş birimleri, sayfa sırasıyla. Yeni çıkarımın metin
        onarımları ('3.14 × 10' → '3.14 × 10^23') eski birimlere de uygulanır ki
        iki taraf aynı biçimde eşleşsin."""
        return cls([_with_fixes(unit, fixes) for unit in PageDocument(old_page).text_units() if unit.get("en")])

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
        return self._single.get(key) or self._joined.get(key) or ""

    def lookup_single(self, text):
        return self._single.get(self.key(text), "")

    @classmethod
    def _first_translations(cls, units):
        """Anahtar → çeviri; aynı anahtarlı birimlerden ilkinin çevirisi kalır."""
        table = {}
        for unit in units:
            table.setdefault(cls.key(unit["en"]), unit["tr"])
        return table


def _with_fixes(unit, fixes):
    en, tr = unit.get("en", ""), unit.get("tr", "")
    for wrong, right in fixes.items():
        en, tr = en.replace(wrong, right), tr.replace(wrong, right)
    return {"en": en, "tr": tr}


def _joined_windows(units):
    """Her birimden başlayan 2..MAX_JOIN uzunluğundaki ardışık grupların birleşimi, sayfa sırasıyla."""
    return [{"en": " ".join(unit["en"] for unit in window), "tr": " ".join(unit["tr"] for unit in window)}
            for start in range(len(units)) for window in _windows(units, start)]


def _windows(units, start):
    return [units[start:start + count] for count in range(2, MAX_JOIN + 1) if start + count <= len(units)]


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
