"""Bir kitap sayfasının çevirmen girdisi: PDF'ten çıkarılan bloklar, bölüm ve
kesit bilgisi, komşu sayfalardan bağlam. prepare_page, migrate_page ve
backfill_images kullanır. Şema: references/FORMAT.md.
"""
import os

import fitz

from extraction.page_extractor import PageExtractor
from extraction.text_utils import normalize_spaces
from project import concepts_settings, extraction_settings

CONTEXT_CHARS = 700
UNKNOWN_CHAPTER = {"num": 0, "en": "", "tr": ""}


def _page_text(document, pdf_page):
    """İlk sayfanın öncesi ve son sayfanın sonrası boş metindir."""
    if not 1 <= pdf_page <= document.page_count:
        return ""
    return normalize_spaces(document[pdf_page - 1].get_text())


def context_snippets(document, pdf_page):
    return {"prev_tail": _page_text(document, pdf_page - 1)[-CONTEXT_CHARS:],
            "next_head": _page_text(document, pdf_page + 1)[:CONTEXT_CHARS]}


class PageInputBuilder:
    """Bir kitap sayfasının çevirmen girdisini kurar; dosyaya ve ilerlemeye yazmaz."""

    def __init__(self, project, progress, extractor):
        self.project = project
        self.progress = progress
        self.extractor = extractor
        self.pdf = project.pdf_path(progress)

    @classmethod
    def for_progress(cls, project, progress):
        return cls(project, progress, PageExtractor(extraction_settings(progress)))

    def hyphen_fixes(self, pdf_page):
        return self.extractor.hyphen_fixes(self.pdf, pdf_page)

    def build(self, page):
        pdf_page = self.pdf_page(page)
        extracted = self.extractor.extract(self.pdf, pdf_page, self.image_dir(page))
        return {"id": f"page-{page}", "page": page, "pdf_page": pdf_page,
                "chapter": self._chapter(page), "section": self._section(page, extracted["running_header"]),
                "title": {"en": "", "tr": ""}, "blocks": extracted["blocks"], "math": extracted["math"],
                "concepts": [], "concepts_spec": concepts_settings(self.progress), "glossary_new": [],
                "context": self._context(pdf_page)}

    def pdf_page(self, page):
        return page + self.progress["pdf_offset"]

    def image_dir(self, page):
        return os.path.join(self.project.work_in, f"page-{page}_images")

    def _chapter(self, page):
        started = [chapter for chapter in self.progress["chapters"] if chapter["start"] <= page]
        if not started:
            return dict(UNKNOWN_CHAPTER)
        return {key: started[-1][key] for key in ("num", "en", "tr")}

    def _section(self, page, header):
        """Koşu başlığı yoksa bölüm açılış sayfasıdır (kesit yok); tek sayfa
        başlığı (Chapter ...) ise kesit önceki sayfadan devam eder."""
        if header is None:
            return {"en": "", "tr": ""}
        if not header["is_chapter"] and header["text"]:
            return {"en": header["text"], "tr": ""}
        previous = self.progress["pages"].get(str(page - 1), {})
        return {"en": previous.get("section_en", ""), "tr": previous.get("section_tr", "")}

    def _context(self, pdf_page):
        with fitz.open(self.pdf) as document:
            return context_snippets(document, pdf_page)
