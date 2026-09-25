"""progress.json'daki kitap ayarları: PDF, çıkarım, kitap bilgisi, kavram
kartları ve çevirmen. Salt okunurdur; ilerleme kaydı Progress'tedir.
"""
from concept_cards import CARD_KINDS
from extraction.settings import with_defaults

DEFAULT_BOOK = {"slug": "kitap", "title": "", "subtitle": "", "subtitle_tr": "",
                "author": "", "series": ""}

_LEGACY_MODE_KINDS = {"code": ["code"], "contrast": ["contrast", "code"], "explain": ["explain"]}
DEFAULT_CODE_COMMENT_LANG = "en"


class InvalidConceptSettings(ValueError):
    """progress.json -> concepts geçersiz bir kart türü ya da mod içeriyor."""


class BookSettings:
    """Ayar bölümleri varsayılanlarla birleşmiş olarak okunur."""

    def __init__(self, data):
        self.data = data

    def book_pdf(self):
        return self.data["book_pdf"]

    def extraction(self):
        return with_defaults(self.data.get("extraction", {}))

    def book(self):
        return {**DEFAULT_BOOK, **self.data.get("book", {})}

    def translator_has_vision(self):
        """Çevirmen model görsel okuyabiliyor mu (denklem PNG'sinden latex üretimi)."""
        return bool(self.data.get("translator", {}).get("vision", True))

    def concepts(self):
        """Kavram kartı ayarları: izinli kart türleri, kod örneği dilleri, kod yorum dili."""
        merged = {"kinds": list(CARD_KINDS),
                  "code_langs": [self.extraction()["default_code_language"]],
                  "code_comment_lang": DEFAULT_CODE_COMMENT_LANG,
                  **self._configured_concepts()}
        _check_card_kinds(merged["kinds"])
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


def _check_card_kinds(kinds):
    """En az bir kart türü olmalı ve hepsi CARD_KINDS'ten olmalı."""
    if not kinds or any(kind not in CARD_KINDS for kind in kinds):
        raise InvalidConceptSettings(f"Geçersiz kart türleri: {kinds!r}; geçerli değerler: {', '.join(CARD_KINDS)}")
