"""Bir kitap sayfasının çevirmen girdisi: PDF'ten çıkarılan bloklar, bölüm ve
kesit bilgisi, komşu sayfalardan bağlam. prepare_page, migrate_page ve
backfill_images kullanır. Şema: references/FORMAT.md.
"""
from extraction.page_extractor import PageExtractor
from extraction.pdf.pymupdf_adapter import PyMuPdfDocument
from extraction.text_utils import normalize_spaces

CONTEXT_CHARS = 700


def _page_text(document, pdf_page):
    """İlk sayfanın öncesi ve son sayfanın sonrası boş metindir."""
    if not 1 <= pdf_page <= document.page_count:
        return ""
    return normalize_spaces(document.page(pdf_page).text())


def context_snippets(document, pdf_page):
    """document: PdfDocument; komşu sayfaların bitişik uçları."""
    return {"prev_tail": _page_text(document, pdf_page - 1)[-CONTEXT_CHARS:],
            "next_head": _page_text(document, pdf_page + 1)[:CONTEXT_CHARS]}


class PageInputBuilder:
    """Bir kitap sayfasının çevirmen girdisini kurar; dosyaya ve ilerlemeye yazmaz."""

    def __init__(self, project, progress, extractor):
        self.project = project
        self.progress = progress
        self.extractor = extractor
        self.pdf = project.pdf_path()

    @classmethod
    def for_progress(cls, project, progress):
        return cls(project, progress, PageExtractor.for_settings(project.load_settings().extraction()))

    def hyphen_fixes(self, pdf_page):
        return self.extractor.hyphen_fixes(self.pdf, pdf_page)

    def build(self, page):
        pdf_page = self.progress.pdf_page(page)
        extracted = self.extractor.extract(self.pdf, pdf_page, self.image_dir(page))
        return {"id": f"page-{page}", "page": page, "pdf_page": pdf_page,
                "chapter": self.progress.chapter_of(page), "section": self._section(page, extracted["running_header"]),
                "title": {"en": "", "tr": ""}, "blocks": extracted["blocks"], "math": extracted["math"],
                "concepts": [], "glossary_new": [],
                "context": self._context(pdf_page)}

    def image_dir(self, page):
        return self.project.work_images(page)

    def _section(self, page, header):
        """Koşu başlığı yoksa bölüm açılış sayfasıdır (kesit yok); tek sayfa
        başlığı (Chapter ...) ise kesit önceki sayfadan devam eder."""
        if header is None:
            return {"en": "", "tr": ""}
        if not header["is_chapter"] and header["text"]:
            return {"en": header["text"], "tr": ""}
        return self.progress.section_of(page - 1)

    def _context(self, pdf_page):
        with PyMuPdfDocument.open(self.pdf) as document:
            return context_snippets(document, pdf_page)
