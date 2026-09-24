"""progress.json: kitap projesinin ilerlemesi ve ayarları, tek doğruluk kaynağı.

JSON bir veri taşıyıcıdır; okuyucu da (data/toc.js üzerinden) okur. Davranışı
Progress taşır: ayarların varsayılanlarla birleşmesi ve sayfa kuralları.
"""
from extraction.settings import with_defaults

DEFAULT_BOOK = {"slug": "kitap", "title": "", "subtitle": "", "subtitle_tr": "",
                "author": "", "series": ""}

CARD_KINDS = ("explain", "contrast", "tradeoff", "code")
_LEGACY_MODE_KINDS = {"code": ["code"], "contrast": ["contrast", "code"], "explain": ["explain"]}
DEFAULT_CODE_COMMENT_LANG = "en"


class InvalidConceptSettings(ValueError):
    """progress.json -> concepts geçersiz bir kart türü ya da mod içeriyor."""


class Progress:
    """progress.json'un içeriği; `data` diske yazılan sözlüktür."""

    def __init__(self, data):
        self.data = data

    def book_pdf(self):
        return self.data["book_pdf"]

    def extraction_settings(self):
        return with_defaults(self.data.get("extraction", {}))

    def book_info(self):
        return {**DEFAULT_BOOK, **self.data.get("book", {})}

    def translator_has_vision(self):
        """Çevirmen model görsel okuyabiliyor mu (denklem PNG'sinden latex üretimi)."""
        return bool(self.data.get("translator", {}).get("vision", True))

    def concepts_settings(self):
        """Kavram kartı ayarları: izinli kart türleri, kod örneği dilleri, kod yorum dili."""
        merged = {"kinds": list(CARD_KINDS),
                  "code_langs": [self.extraction_settings()["default_code_language"]],
                  "code_comment_lang": DEFAULT_CODE_COMMENT_LANG,
                  **self._configured_concepts()}
        unknown = [kind for kind in merged["kinds"] if kind not in CARD_KINDS]
        if unknown or not merged["kinds"]:
            raise InvalidConceptSettings(f"Geçersiz kart türleri: {merged['kinds']!r}; "
                                         f"geçerli değerler: {', '.join(CARD_KINDS)}")
        return merged

    def _configured_concepts(self):
        """progress.json -> concepts; eski tek `mode` anahtarı izinli tür listesine çevrilir."""
        configured = dict(self.data.get("concepts", {}))
        mode = configured.pop("mode", None)
        if mode is None or "kinds" in configured:
            return configured
        if mode not in _LEGACY_MODE_KINDS:
            raise InvalidConceptSettings(f"Bilinmeyen kavram kartı modu: {mode!r}")
        return {**configured, "kinds": _LEGACY_MODE_KINDS[mode]}
