"""PDF'siz testler için `PdfDocument` / `PdfPage` / `LayoutReader` sahteleri ve düz veri kurucuları.

Kutular sol-üst orijinli (x0, y0, x1, y1) demetleriyle verilir. Gerçek PDF
gereken sınır testleri `real_page` ile PyMuPDF adaptörünü kullanır.
"""
import contextlib
import dataclasses

import _paths  # noqa: F401
from extraction.pdf import geometry
from extraction.pdf.model import Drawing, LayoutElement, PageLayout, Span
from extraction.pdf.ports import FIRST_PAGE_NUMBER
from extraction.pdf.pymupdf_adapter import PyMuPdfDocument

FAKE_PNG = b"\x89PNG fake"
FAKE_PDF = "fake.pdf"
PAGE_WIDTH = 600.0
PAGE_HEIGHT = 800.0
FONT = "Helvetica"
SIZE = 10.0


def span(text, box):
    """FONT'ta SIZE puntoluk parça; satırı kendi üst kenarı, taban çizgisi kendi alt kenarıdır.
    Fontu in_font, puntosu sized değiştirir."""
    return Span(text, FONT, SIZE, geometry.Box(*box), box[1], box[3])


def in_font(font, piece):
    """Aynı parça (Span ya da LayoutElement) başka fontta."""
    return dataclasses.replace(piece, font=font)


def sized(size, piece):
    """Aynı parça başka puntoda."""
    return dataclasses.replace(piece, size=size)


def fill(*box):
    return Drawing(geometry.Box(*box), is_filled=True)


def stroke(*box):
    return Drawing(geometry.Box(*box), is_filled=False)


def element(text, box):
    """Düzen okuyucusunun paragraf öğesi; türünü of_kind, öteki alanlarını dataclasses.replace değiştirir."""
    return LayoutElement("paragraph", geometry.Box(*box), text)


def of_kind(kind, item):
    """Aynı öğe başka türde: heading, list, list item, image…"""
    return dataclasses.replace(item, kind=kind)


class FakePdfPage:
    """Satırları ve çizimleri elle verilen sayfa: FAKE_PDF'in PAGE_WIDTH × PAGE_HEIGHT boyutlu,
    numarası verilen sayfası. Kırpılan görüntü sabit baytlardır."""

    def __init__(self, lines=(), shapes=(), number=FIRST_PAGE_NUMBER):
        self._lines = [tuple(line) for line in lines]
        self._shapes = list(shapes)
        self._number = number

    @property
    def pdf_path(self):
        return FAKE_PDF

    @property
    def number(self):
        return self._number

    @property
    def width(self):
        return PAGE_WIDTH

    @property
    def height(self):
        return PAGE_HEIGHT

    def text_lines(self):
        return list(self._lines)

    def text(self):
        return "\n".join(" ".join(s.text for s in line) for line in self._lines)

    def drawings(self):
        return list(self._shapes)

    def text_in(self, box):
        return " ".join(s.text for line in self._lines for s in line if geometry.intersects(box, s.box))

    def png(self, box, dpi):
        return FAKE_PNG


class FakePdfDocument:
    """Sayfaları elle verilen, metadata'sı boş belge; `with` ile açılıp kapanır gibi davranır.
    Gerçek belge gibi yolunu tutmaz: pdf_path yalnız açıcının verdiği yoldur, saklanmaz."""

    def __init__(self, pages=(), pdf_path=FAKE_PDF):
        self._pages = list(pages)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    @property
    def page_count(self):
        return len(self._pages)

    @property
    def metadata(self):
        return {}

    def has_page(self, number):
        return FIRST_PAGE_NUMBER <= number <= self.page_count

    def page(self, number):
        return self._pages[number - FIRST_PAGE_NUMBER]

    def page_text(self, number):
        return self._pages[number - FIRST_PAGE_NUMBER].text()


class FakeLayoutReader:
    """Önceden verilen öğeleri sayfanın düzeni olarak döndürür."""

    def __init__(self, elements=()):
        self._elements = tuple(elements)

    def read(self, page, image_dir):
        return PageLayout(page.height, self._elements)


@contextlib.contextmanager
def real_page(pdf_path, number=1):
    with PyMuPdfDocument.open(pdf_path) as document:
        yield document.page(number)
