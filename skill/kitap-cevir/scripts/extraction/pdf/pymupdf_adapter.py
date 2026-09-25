"""PyMuPDF adaptörü: `PdfDocument` / `PdfPage` arayüzlerini PyMuPDF ile karşılar;
diskteki görselin boyutunu da okur. PyMuPDF'in koordinatları zaten sol-üst orijinlidir."""
import fitz

from extraction.pdf.geometry import Box
from extraction.pdf.model import Drawing, Span

FIRST_PAGE_NUMBER = 1       # PdfPage sayfaları 1'den, PyMuPDF 0'dan sayar


class PyMuPdfDocument:
    """Açık bir PDF; sayfalarını `PdfPage` olarak verir. `with` bloğunun sonunda kapanır."""

    def __init__(self, document):
        self._document = document

    @classmethod
    def open(cls, pdf_path):
        return cls(fitz.open(pdf_path))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._document.close()

    @property
    def page_count(self):
        return self._document.page_count

    @property
    def metadata(self):
        return self._document.metadata or {}

    def page(self, number):
        return PyMuPdfPage(self._document[number - FIRST_PAGE_NUMBER])

    def page_text(self, number):
        return self.page(number).text()


class PyMuPdfPage:
    def __init__(self, page):
        self.pdf_path = page.parent.name
        self.number = page.number + FIRST_PAGE_NUMBER
        self._page = page
        self.width = page.rect.width
        self.height = page.rect.height

    def text_lines(self):
        lines = (line for block in self._page.get_text("dict")["blocks"] for line in block.get("lines", []))
        return [spans for spans in map(self._spans, lines) if spans]

    @staticmethod
    def _spans(line):
        return tuple(Span(raw["text"], raw["font"], raw["size"], _box(raw["bbox"]), line["bbox"][1], raw["origin"][1])
                     for raw in line["spans"] if raw["text"].strip())

    def text(self):
        return self._page.get_text()

    def drawings(self):
        return [Drawing(_box(drawing["rect"]), bool(drawing.get("fill"))) for drawing in self._page.get_drawings()]

    def text_in(self, box):
        return self._page.get_text("text", clip=_rect(box))

    def png(self, box, dpi):
        return self._page.get_pixmap(dpi=dpi, clip=_rect(box)).tobytes("png")


def image_size(path):
    """Diskteki görselin piksel boyutu: (genişlik, yükseklik)."""
    pixmap = fitz.Pixmap(path)
    return pixmap.width, pixmap.height


def _box(rect):
    x0, y0, x1, y1 = rect
    return Box(x0, y0, x1, y1)


def _rect(box):
    return fitz.Rect(box.x0, box.y0, box.x1, box.y1)
