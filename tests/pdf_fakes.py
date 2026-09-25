"""PDF'siz testler için `PdfDocument` / `PdfPage` / `LayoutReader` sahteleri ve düz veri kurucuları.

Kutular sol-üst orijinli (x0, y0, x1, y1) demetleriyle verilir. Gerçek PDF
gereken sınır testleri `real_page` ile PyMuPDF adaptörünü kullanır.
"""
import contextlib
from dataclasses import dataclass, field

import _paths  # noqa: F401
from extraction.pdf.geometry import Box
from extraction.pdf.model import Drawing, LayoutElement, PageLayout, Span
from extraction.pdf.pymupdf_adapter import PyMuPdfDocument

FAKE_PNG = b"\x89PNG fake"
PAGE_WIDTH = 600.0
PAGE_HEIGHT = 800.0


def span(text, box, font="Helvetica", size=10.0):
    """Satırı kendi üst kenarı, taban çizgisi kendi alt kenarı olan parça."""
    return Span(text, font, size, Box(*box), box[1], box[3])


def fill(*box):
    return Drawing(Box(*box), is_filled=True)


def stroke(*box):
    return Drawing(Box(*box), is_filled=False)


def element(text, box, kind="paragraph", **fields):
    return LayoutElement(kind, Box(*box), text, **fields)


@dataclass
class FakePdfPage:
    """Satırları ve çizimleri elle verilen sayfa; kırpılan görüntü sabit baytlardır."""
    lines: list = field(default_factory=list)
    shapes: list = field(default_factory=list)
    width: float = PAGE_WIDTH
    height: float = PAGE_HEIGHT
    pdf_path: str = "fake.pdf"
    number: int = 1

    def text_lines(self):
        return [tuple(line) for line in self.lines]

    def text(self):
        return "\n".join(" ".join(s.text for s in line) for line in self.lines)

    def drawings(self):
        return list(self.shapes)

    def text_in(self, box):
        return " ".join(s.text for line in self.lines for s in line if box.intersects(s.box))

    def png(self, box, dpi):
        return FAKE_PNG


@dataclass
class FakePdfDocument:
    """Sayfaları elle verilen belge; `with` ile açılıp kapanır gibi davranır."""
    pages: list = field(default_factory=list)
    pdf_path: str = "fake.pdf"
    metadata: dict = field(default_factory=dict)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    @property
    def page_count(self):
        return len(self.pages)

    def page(self, number):
        return self.pages[number - 1]

    def page_text(self, number):
        return self.pages[number - 1].text()


@dataclass
class FakeLayoutReader:
    """Önceden verilen öğeleri sayfanın düzeni olarak döndürür."""
    elements: tuple = ()

    def read(self, page, image_dir):
        return PageLayout(page.height, tuple(self.elements))


@contextlib.contextmanager
def real_page(pdf_path, number=1):
    with PyMuPdfDocument.open(pdf_path) as document:
        yield document.page(number)
