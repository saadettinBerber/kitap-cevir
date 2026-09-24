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
UNKNOWN_CHAPTER = {"num": 0, "en": "", "tr": ""}


class InvalidConceptSettings(ValueError):
    """progress.json -> concepts geçersiz bir kart türü ya da mod içeriyor."""


class Progress:
    """progress.json'un içeriği; `data` diske yazılan sözlüktür."""

    def __init__(self, data):
        self.data = data

    def book_pdf(self):
        return self.data["book_pdf"]

    def pdf_page(self, page):
        return page + self.data["pdf_offset"]

    def chapter_of(self, page):
        """Sayfanın içinde bulunduğu bölüm; ilk bölümden önceki sayfanın bölümü yoktur."""
        started = [chapter for chapter in self.data["chapters"] if chapter["start"] <= page]
        if not started:
            return dict(UNKNOWN_CHAPTER)
        return {key: started[-1][key] for key in ("num", "en", "tr")}

    def section_of(self, page):
        """Kaydedilmiş sayfanın kesiti; kaydı olmayan sayfanın kesiti boştur."""
        entry = self.data["pages"].get(str(page), {})
        return {"en": entry.get("section_en", ""), "tr": entry.get("section_tr", "")}

    def pages_per_run(self):
        return self.data.get("pages_per_run", 1)

    def next_pages(self, count):
        """Son kaydedilen sayfadan sonraki en çok count sayfa; kitabın sonunu aşmaz."""
        start = self.data["last_translated_page"] + 1
        end = min(start + count - 1, self.data["book_total_pages"])
        return list(range(start, end + 1))

    def mark_blank(self, page):
        self._record(page, {"blank": True, "pdf_page": self.pdf_page(page)})

    def record_translation(self, document):
        """Çevrilmiş sayfa belgesinden içindekiler kaydı (başlık, kesit, bölüm)."""
        title, section = document.get("title", {}), document.get("section", {})
        self._record(document["page"], {
            "pdf_page": document["pdf_page"], "chapter": document.get("chapter", {}).get("num"),
            "title_en": title.get("en", ""), "title_tr": title.get("tr", ""),
            "section_en": section.get("en", ""), "section_tr": section.get("tr", "")})

    def _record(self, page, entry):
        """Sayfa kaydedilir; son çevrilen sayfa yalnız ileri gider."""
        self.data["pages"][str(page)] = entry
        self.data["last_translated_page"] = max(self.data["last_translated_page"], page)

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
