"""progress.json'daki ilerleme kaydı: çevrilen ve boş sayfalar, son çevrilen
sayfa, bölümler. Tek doğruluk kaynağıdır; JSON bir veri taşıyıcıdır, okuyucu da
(data/toc.js üzerinden) okur. Kitap ayarları BookSettings'tedir.
"""
UNKNOWN_CHAPTER = {"num": 0, "en": "", "tr": ""}


class Progress:
    """İlerleme kaydı; `data` diske yazılan sözlüğün tamamıdır."""

    def __init__(self, data):
        self.data = data

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

    def translated_pages(self):
        """Kaydedilmiş, boş olmayan sayfalar, sırayla."""
        return sorted(int(page) for page, entry in self.data["pages"].items() if not entry.get("blank"))

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
