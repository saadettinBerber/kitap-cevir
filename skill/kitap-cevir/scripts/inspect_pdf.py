"""PDF'i tanımak için yardımcı: sayfa sayısı, sayfa metni, düzen dökümü ve
kitap sayfası / PDF sayfası ofset tahmini. Yeni bir kitap kurarken
(init) ve extraction ayarlarını akort ederken kullanılır.

Kullanım:
  python3 inspect_pdf.py kitap.pdf info
  python3 inspect_pdf.py kitap.pdf text 5-9         PDF sayfalarının düz metni (içindekiler okumak için)
  python3 inspect_pdf.py kitap.pdf layout 40        satır satır: y, ODL y, font, boyut, metin
  python3 inspect_pdf.py kitap.pdf offset [--from 20 --to 200]
                                                    basılı sayfa numarasından ofset tahmini
"""
import argparse
import re
from collections import Counter
from dataclasses import dataclass

from extraction.pdf.pymupdf_adapter import PyMuPdfDocument

EDGE_LINES = 2                    # sayfa başı/sonu kaç satırda folyo aranır
MAX_FOLIO = 9999
TEXT_PREVIEW_CHARS = 70
TOP_CANDIDATES = 3
_EDGE_NUMBER = re.compile(r"^(\d{1,4})\b|\b(\d{1,4})$")


def _page_range(spec, total):
    if "-" in spec:
        start, end = spec.split("-", 1)
        return range(int(start), min(int(end), total) + 1)
    return range(int(spec), int(spec) + 1)


def _lines(page):
    """page: PdfPage → satırlar (Span demetleri), yukarıdan aşağı, soldan sağa."""
    return sorted(page.text_lines(), key=lambda spans: (round(spans[0].line_y), min(s.box.x0 for s in spans)))


def _line_text(spans):
    return "".join(span.text for span in spans).strip()


def _font_usage(lines):
    """(font, boyut) -> karakter sayısı."""
    usage = Counter()
    for span in (span for spans in lines for span in spans):
        usage[(span.font, round(span.size, 1))] += len(span.text)
    return usage


def _edge_lines(lines):
    """Sayfanın ilk ve son satırları; kısa sayfada bir satır iki kez alınmaz."""
    return lines[:EDGE_LINES] + lines[EDGE_LINES:][-EDGE_LINES:]


def _folio_candidates(lines):
    """Sayfanın ilk ve son satırlarındaki basılı sayfa numarası adayları."""
    matches = (_EDGE_NUMBER.search(_line_text(spans)) for spans in _edge_lines(lines))
    numbers = [int(match.group(1) or match.group(2)) for match in matches if match]
    return [number for number in numbers if 0 < number <= MAX_FOLIO]


class FolioOffsets:
    """Basılı sayfa numaralarından ofset oyları (PDF sayfası - kitap sayfası)."""

    def __init__(self, votes, examples):
        self.votes = votes
        self.examples = examples

    @classmethod
    def of_folios(cls, folios):
        """folios: (PDF sayfası, basılı numara) çiftleri; eksi ofset sayılmaz."""
        votes, examples = Counter(), {}
        for pdf_page, folio in folios:
            offset = pdf_page - folio
            if offset >= 0:
                votes[offset] += 1
                examples.setdefault(offset, (pdf_page, folio))
        return cls(votes, examples)

    def most_likely(self, count):
        """[(ofset, oy, ilk örnek)], en çok oy alan önce."""
        return [(offset, votes, self.examples[offset]) for offset, votes in self.votes.most_common(count)]


@dataclass(frozen=True)
class LineInfo:
    """Bir satırın dökümü: üst kenarı, sayfanın altından yüksekliği (odlY), ilk parçanın puntosu ile fontu, metni."""
    y: float
    odl_y: float
    size: float
    font: str
    text: str

    @classmethod
    def of(cls, spans, page_height):
        first = spans[0]
        return cls(first.line_y, page_height - max(span.box.y1 for span in spans), first.size, first.font,
                   _line_text(spans))


class PdfInspector:
    """Açık bir PDF'in (PdfDocument) tanıma bilgileri; okur, basmaz."""

    def __init__(self, document):
        self.document = document

    def page_count(self):
        return self.document.page_count

    def page_size(self):
        first = self.document.page(1)
        return first.width, first.height

    def metadata(self):
        """Boş olmayan metadata alanları."""
        return {key: value for key, value in self.document.metadata.items() if value}

    def page_texts(self, pages):
        """[(PDF sayfası, düz metin)]; pages '5' ya da '5-9'."""
        return [(number, self.document.page(number).text()) for number in _page_range(pages, self.page_count())]

    def lines(self, number):
        page = self.document.page(number)
        return [LineInfo.of(spans, page.height) for spans in _lines(page)]

    def font_usage(self, number):
        """[((font, boyut), karakter sayısı)], en çok kullanılan önce."""
        return _font_usage(_lines(self.document.page(number))).most_common()

    def offsets(self, first, last):
        return FolioOffsets.of_folios(self._folios(first, last))

    def _folios(self, first, last):
        """(PDF sayfası, basılı sayfa numarası) adayları."""
        numbers = range(first, min(last, self.page_count()) + 1)
        return [(number, folio) for number in numbers for folio in _folio_candidates(_lines(self.document.page(number)))]


class InspectionReport:
    """PdfInspector'ın okuduklarını ekrana basar: info, text, layout, offset."""

    def __init__(self, inspector):
        self.inspector = inspector

    def info(self):
        width, height = self.inspector.page_size()
        print(f"PDF sayfa sayısı: {self.inspector.page_count()}")
        print(f"Sayfa boyutu (pt): {width:.1f} x {height:.1f}")
        for key, value in self.inspector.metadata().items():
            print(f"  {key}: {value}")

    def text(self, pages):
        for number, text in self.inspector.page_texts(pages):
            print(f"===== PDF sayfa {number} =====")
            print(text)

    def layout(self, number):
        for line in self.inspector.lines(number):
            print(f"y={line.y:6.1f}  odlY={line.odl_y:6.1f}  size={line.size:5.2f}  "
                  f"{line.font[:22]:22}  {line.text[:TEXT_PREVIEW_CHARS]}")
        print("\nFont / boyut / karakter sayısı:")
        for (font, size), count in self.inspector.font_usage(number):
            print(f"  {font:28} {size:5.1f}  {count}")

    def offset(self, first, last):
        candidates = self.inspector.offsets(first, last).most_likely(TOP_CANDIDATES)
        if not candidates:
            print("Basılı sayfa numarası bulunamadı; ofseti elle belirleyin.")
            return
        print("Olası ofsetler (PDF sayfası - kitap sayfası):")
        for offset, count, (pdf_page, folio) in candidates:
            print(f"  offset={offset:4}  {count:4} oy   örnek: PDF {pdf_page} = kitap {folio}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info").set_defaults(run=lambda report, args: report.info())
    text = commands.add_parser("text")
    text.add_argument("pages", help="örn. 5 veya 5-9 (PDF sayfaları)")
    text.set_defaults(run=lambda report, args: report.text(args.pages))
    layout = commands.add_parser("layout")
    layout.add_argument("page", type=int, help="PDF sayfası")
    layout.set_defaults(run=lambda report, args: report.layout(args.page))
    offset = commands.add_parser("offset")
    offset.add_argument("--from", dest="first", type=int, default=1)
    offset.add_argument("--to", dest="last", type=int, default=400)
    offset.set_defaults(run=lambda report, args: report.offset(args.first, args.last))
    return parser.parse_args()


def main():
    args = parse_args()
    with PyMuPdfDocument.open(args.pdf) as document:
        args.run(InspectionReport(PdfInspector(document)), args)


if __name__ == "__main__":
    main()
