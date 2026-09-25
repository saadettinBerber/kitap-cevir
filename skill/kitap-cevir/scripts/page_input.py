"""Bir kitap sayfasının çevirmen girdisi: PDF'ten çıkarılan bloklar, bölüm ve
kesit bilgisi, komşu sayfalardan bağlam. prepare_page, migrate_page ve
backfill_images kullanır. Şema: references/FORMAT.md.
"""
from book_pdf import BookPdf


class PageInputBuilder:
    """Bir kitap sayfasının çevirmen girdisini kurar; görseller dışında dosyaya ve ilerlemeye yazmaz."""

    def __init__(self, progress, book_pdf):
        self.progress = progress
        self.book_pdf = book_pdf

    @classmethod
    def for_progress(cls, project, progress):
        return cls(progress, BookPdf.for_project(project))

    def hyphen_fixes(self, pdf_page):
        return self.book_pdf.hyphen_fixes(pdf_page)

    def build(self, page, image_dir):
        """Sayfanın görselleri image_dir'e yazılır, girdi bu adlarla onlara bağlanır."""
        pdf_page = self.progress.pdf_page(page)
        extracted = self.book_pdf.extract(pdf_page, image_dir)
        return {"id": f"page-{page}", "page": page, "pdf_page": pdf_page,
                "chapter": self.progress.chapter_of(page), "section": self._section(page, extracted["running_header"]),
                "title": {"en": "", "tr": ""}, "blocks": extracted["blocks"], "math": extracted["math"],
                "concepts": [], "glossary_new": [],
                "context": extracted["context"]}

    def _section(self, page, header):
        """Koşu başlığı yoksa bölüm açılış sayfasıdır (kesit yok); tek sayfa
        başlığı (Chapter ...) ise kesit önceki sayfadan devam eder."""
        if header is None:
            return {"en": "", "tr": ""}
        if not header["is_chapter"] and header["text"]:
            return {"en": header["text"], "tr": ""}
        return self.progress.section_of(page - 1)
