"""Kitabın PDF'i: bir sayfanın çıkarımı ve komşu sayfalardan bağlam metni.

PDF yalnız burada açılır; açıcı yapıcıdan verilir, testler sahte belge verir.
page_input kullanır.
"""
import functools

from extraction.page_extractor import PageExtractor
from extraction.pdf.ports import FIRST_PAGE_NUMBER
from extraction.pdf.pymupdf_adapter import PyMuPdfDocument
from extraction.text_utils import normalize_spaces

CONTEXT_CHARS = 700


class BookPdf:
    """Kitabın PDF'inden sayfa okur; her çağrı belgeyi bir kez açar."""

    def __init__(self, open_pdf, extractor):
        """open_pdf() -> PdfDocument (with bloğunda kapanır); extractor: PageExtractor."""
        self._open_pdf = open_pdf
        self._extractor = extractor

    @classmethod
    def for_project(cls, project):
        """Kurulum: ayarlar projeden bir kez yüklenip okuyucuyu kuran fabrikaya verilir."""
        return cls._for_settings(project.pdf_path(), project.load_settings())

    @classmethod
    def _for_settings(cls, pdf_path, settings):
        return cls(functools.partial(PyMuPdfDocument.open, pdf_path), PageExtractor.for_settings(settings.extraction()))

    def extract(self, pdf_page, image_dir):
        """{blocks, running_header, math, context}; görseller image_dir'e yazılır."""
        with self._open_pdf() as document:
            extracted = self._extractor.extract(document.page(pdf_page), image_dir)
            return {**extracted, "context": context_snippets(document, pdf_page)}

    def hyphen_fixes(self, pdf_page):
        with self._open_pdf() as document:
            return self._extractor.hyphen_fixes(document.page(pdf_page))


def context_snippets(document, pdf_page):
    """document: PdfDocument; komşu sayfaların bitişik uçları."""
    return {"prev_tail": _page_text(document, pdf_page - 1)[-CONTEXT_CHARS:],
            "next_head": _page_text(document, pdf_page + 1)[:CONTEXT_CHARS]}


def _page_text(document, pdf_page):
    """İlk sayfanın öncesi ve son sayfanın sonrası boş metindir."""
    if not FIRST_PAGE_NUMBER <= pdf_page <= document.page_count:
        return ""
    return normalize_spaces(document.page_text(pdf_page))
