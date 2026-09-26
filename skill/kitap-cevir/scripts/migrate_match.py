"""Eski çevrilmiş sayfadaki en→tr eşleşmelerini yeni çıkarım yapısına taşır.

Eski sayfanın tüm metin birimleri (cümle, başlık, caption, dipnot, liste
maddesi, tablo hücresi) sıralı bir listeye düzleştirilir. Yeni birim için
önce birebir, sonra normalize eşleşme; yeni cümle eski birimlerin birleşimine
ya da eski birim yeni cümlelerin birleşimine eşitse birleştirilerek taşınır.
Eşleşmeyen birimler `pending` listesine düşer (küçük bir çeviri geçişi için).
"""
import re

from extraction.text_utils import clean_ligatures, normalize_spaces
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
    """Yeni birimin eski çevirisini söyler; birime yazmak bloğun işidir (Block.fill). Çevirisi boş kalan
    birimler doldurmadan sonra pending'den okunur."""

    def __init__(self, translations):
        self._translations = translations

    def translation(self, en):
        """Birime yazılacak çeviri; metin yoksa, çeviri bulunamazsa ya da yer tutucu eksikse boş."""
        if not _has_text(en):
            return ""
        translation = self._old_translation(en)
        return translation if _keeps_placeholders(en, translation) else ""

    def merged_sentences(self, sentences):
        """Ardışık yeni cümlelerin birleşimi eski bir birime eşitse tek cümle olur."""
        merged, index = [], 0
        while index < len(sentences):
            unit, taken = self._merge_run(sentences, index)
            merged.append(unit)
            index += taken
        return merged

    def pending(self, unit_paths):
        """Doldurulmuş (yol, birim) çiftlerinden metni olup çevirisi boş kalanlar: {path, en, tr_hint}."""
        return [{"path": path, "en": unit["en"], "tr_hint": self._old_translation(unit["en"])}
                for path, unit in unit_paths if _has_text(unit["en"]) and not unit["tr"]]

    def _old_translation(self, en):
        """Eski çeviri; bulunamazsa ve hücre yalnız sayıysa İngilizcesi aynen kalır."""
        translation = self._translations.lookup(en)
        if not translation and NUMERIC_CELL.match(en):
            return en
        return translation

    def _merge_run(self, sentences, index):
        """(birim, kapsadığı cümle sayısı): tek başına bulunan cümle kendisidir; değilse eski bir
        birime eşit en uzun birleşim, o da yoksa yine kendisi."""
        if self._translations.lookup(sentences[index]["en"]):
            return sentences[index], 1
        for count in range(min(MAX_JOIN, len(sentences) - index), 1, -1):
            joined = " ".join(sentence["en"] for sentence in sentences[index:index + count])
            if self._translations.lookup_single(joined):
                return {**sentences[index], "en": joined}, count
        return sentences[index], 1


def _has_text(en):
    return bool((en or "").strip())


def _keeps_placeholders(en, translation):
    """⟦eq-N⟧ taşıyan metnin çevirisi de yer tutucuyu taşımalı; yoksa denklem kaybolur."""
    return not PLACEHOLDER.search(en) or bool(PLACEHOLDER.search(translation))
