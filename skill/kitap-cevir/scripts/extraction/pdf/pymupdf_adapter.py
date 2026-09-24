"""PyMuPDF adaptörü: `PdfPage` arayüzünü bir PyMuPDF sayfasıyla karşılar.
PyMuPDF'in koordinatları zaten sol-üst orijinlidir."""
import fitz

from extraction.pdf.geometry import Box
from extraction.pdf.model import Drawing, Span


class PyMuPdfDocument:
    """Açık bir PDF; sayfalarını `PdfPage` olarak verir. `with` bloğunun sonunda kapanır."""

    def __init__(self, pdf_path, document):
        self.pdf_path = pdf_path
        self.document = document

    @classmethod
    def open(cls, pdf_path):
        return cls(pdf_path, fitz.open(pdf_path))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.document.close()

    def page(self, number):
        return PyMuPdfPage(self.pdf_path, number, self.document[number - 1])


class PyMuPdfPage:
    def __init__(self, pdf_path, number, page):
        self.pdf_path = pdf_path
        self.number = number
        self.page = page
        self.height = page.rect.height

    def text_lines(self):
        lines = (line for block in self.page.get_text("dict")["blocks"] for line in block.get("lines", []))
        return [spans for spans in map(self._spans, lines) if spans]

    @staticmethod
    def _spans(line):
        return tuple(Span(raw["text"], raw["font"], raw["size"], _box(raw["bbox"]), line["bbox"][1])
                     for raw in line["spans"] if raw["text"].strip())

    def drawings(self):
        return [Drawing(_box(drawing["rect"]), bool(drawing.get("fill"))) for drawing in self.page.get_drawings()]

    def text_in(self, box):
        return self.page.get_text("text", clip=_rect(box))

    def png(self, box, dpi):
        return self.page.get_pixmap(dpi=dpi, clip=_rect(box)).tobytes("png")


def _box(rect):
    x0, y0, x1, y1 = rect
    return Box(x0, y0, x1, y1)


def _rect(box):
    return fitz.Rect(box.x0, box.y0, box.x1, box.y1)
