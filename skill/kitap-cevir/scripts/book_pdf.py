"""Kitabın PDF'i: bir sayfanın çıkarımı ve komşu sayfalardan bağlam metni.

PDF yalnız burada açılır; açıcı yapıcıdan verilir, testler sahte belge verir.
page_input kullanır.
"""
import functools

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


class BookPdf:
    """Kitabın PDF'inden sayfa okur; her çağrı belgeyi bir kez açar."""

    def __init__(self, open_pdf, extractor):
        """open_pdf() -> PdfDocument (with bloğunda kapanır); extractor: PageExtractor."""
        self.open_pdf = open_pdf
        self.extractor = extractor

    @classmethod
    def for_project(cls, project):
        return cls(functools.partial(PyMuPdfDocument.open, project.pdf_path()),
                   PageExtractor.for_settings(project.load_settings().extraction()))

    def extract(self, pdf_page, image_dir):
        """{blocks, running_header, math, context}; görseller image_dir'e yazılır."""
        with self.open_pdf() as document:
            extracted = self.extractor.extract_page(document.page(pdf_page), image_dir)
            return {**extracted, "context": context_snippets(document, pdf_page)}

    def hyphen_fixes(self, pdf_page):
        with self.open_pdf() as document:
            return self.extractor.hyphen_fixes(document.page(pdf_page))
