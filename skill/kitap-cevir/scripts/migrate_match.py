"""Eski çevrilmiş sayfadaki en→tr eşleşmelerini yeni çıkarım yapısına taşır.

Eski sayfanın tüm metin birimleri (cümle, başlık, caption, dipnot, liste
maddesi, tablo hücresi) sıralı bir listeye düzleştirilir. Yeni birim için
önce birebir, sonra normalize eşleşme; yeni cümle eski birimlerin birleşimine
ya da eski birim yeni cümlelerin birleşimine eşitse birleştirilerek taşınır.
Eşleşmeyen birimler `pending` listesine düşer (küçük bir çeviri geçişi için).
"""
import re

from extraction.text_utils import clean_ligatures, normalize_spaces

MAX_JOIN = 4
NUMERIC_CELL = re.compile(r"^(?:[\d.,%~+\-–\s]|<br>)*$")
PLACEHOLDER = re.compile(r"⟦eq-\d+⟧")
_TAGS = re.compile(r"<[^>]+>")
_TEXT_TYPES = ("heading", "caption", "footnote", "chapter")


def normalize(text):
    text = PLACEHOLDER.sub(" ", _TAGS.sub(" ", clean_ligatures(text or "")))
    return normalize_spaces(text.replace("`", "").replace("’", "'").replace("“", '"')
                            .replace("”", '"')).lower().strip(" .")


def old_units(blocks):
    """Eski sayfanın çevrilmiş birimleri, sayfa sırasıyla."""
    units = []
    for block in blocks:
        if block["type"] == "para":
            units += block["sentences"]
        elif block["type"] == "list":
            units += block["items"]
        elif block["type"] == "table":
            units += [cell for row in block["rows"] for cell in row]
        elif block["type"] in _TEXT_TYPES:
            units.append(block)
    return [{"en": u.get("en", ""), "tr": u.get("tr", "")} for u in units if u.get("en")]


def apply_fixes(units, fixes):
    """Yeni çıkarımın metin onarımlarını ('3.14 × 10' → '3.14 × 10^23') eski
    birimlere de uygular ki her iki taraf aynı biçimde eşleşsin."""
    for unit in units:
        for wrong, right in fixes.items():
            unit["en"] = unit["en"].replace(wrong, right)
            unit["tr"] = unit["tr"].replace(wrong, right)
    return units


class Translations:
    """Eski birimlerden kurulan arama tabloları."""

    def __init__(self, units):
        self.single = {}
        self.joined = {}
        for index, unit in enumerate(units):
            self.single.setdefault(normalize(unit["en"]), unit["tr"])
            for count in range(2, MAX_JOIN + 1):
                window = units[index:index + count]
                if len(window) == count:
                    key = normalize(" ".join(u["en"] for u in window))
                    self.joined.setdefault(key, " ".join(u["tr"] for u in window))

    def lookup(self, text):
        key = normalize(text)
        if not key:
            return ""
        return self.single.get(key) or self.joined.get(key) or ""

    def lookup_single(self, text):
        return self.single.get(normalize(text), "")


def _needs_placeholder(unit, translation):
    return bool(PLACEHOLDER.search(unit["en"])) and not PLACEHOLDER.search(translation)


def fill_unit(unit, translations, pending, path):
    """Birime tr yazar; bulunamazsa ya da yer tutucu eksikse pending'e ekler."""
    if not (unit["en"] or "").strip():
        unit["tr"] = ""
        return True
    translation = translations.lookup(unit["en"])
    if not translation and NUMERIC_CELL.match(unit["en"]):
        translation = unit["en"]
    if translation and not _needs_placeholder(unit, translation):
        unit["tr"] = translation
        return True
    unit["tr"] = ""
    pending.append({"path": path, "en": unit["en"], "tr_hint": translation})
    return False


def fill_sentences(sentences, translations, pending, path):
    """Ardışık yeni cümlelerin birleşimi eski bir birime eşitse tek cümle olur."""
    merged, index = [], 0
    while index < len(sentences):
        unit, taken = _merge_run(sentences, index, translations)
        fill_unit(unit, translations, pending, f"{path}.sentences[{len(merged)}]")
        merged.append(unit)
        index += taken
    return merged


def _merge_run(sentences, index, translations):
    if translations.lookup(sentences[index]["en"]):
        return sentences[index], 1
    for count in range(MAX_JOIN, 1, -1):
        window = sentences[index:index + count]
        joined = " ".join(s["en"] for s in window)
        if len(window) == count and translations.lookup_single(joined):
            return {**sentences[index], "en": joined}, count
    return sentences[index], 1
