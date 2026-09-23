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

import fitz

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
    lines = [record for block in page.get_text("dict")["blocks"]
             for line in block.get("lines", []) for record in _line_record(line)]
    lines.sort(key=lambda ln: (round(ln["bbox"][1]), ln["bbox"][0]))
    return lines


def _line_record(line):
    """[satır kaydı]; yalnız boşluktan oluşan satır kayıt üretmez."""
    spans = [s for s in line["spans"] if s["text"].strip()]
    if not spans:
        return []
    return [{"bbox": line["bbox"], "spans": spans, "text": "".join(s["text"] for s in spans).strip()}]


def _line_row(line, height):
    span = line["spans"][0]
    odl_y = height - line["bbox"][3]
    return (f"y={line['bbox'][1]:6.1f}  odlY={odl_y:6.1f}  size={span['size']:5.2f}  "
            f"{span['font'][:22]:22}  {line['text'][:TEXT_PREVIEW_CHARS]}")


def _font_usage(lines):
    """(font, boyut) -> karakter sayısı."""
    usage = Counter()
    for span in (span for line in lines for span in line["spans"]):
        usage[(span["font"], round(span["size"], 1))] += len(span["text"])
    return usage


def _folio_candidates(lines):
    """Sayfanın ilk ve son satırlarındaki basılı sayfa numarası adayları."""
    matches = (_EDGE_NUMBER.search(line["text"]) for line in lines[:EDGE_LINES] + lines[-EDGE_LINES:])
    numbers = [int(match.group(1) or match.group(2)) for match in matches if match]
    return [number for number in numbers if 0 < number <= MAX_FOLIO]


class PdfInspector:
    """Açık bir PDF üzerinde tanıma komutları: info, text, layout, offset."""

    def __init__(self, document):
        self.document = document

    def info(self):
        print(f"PDF sayfa sayısı: {self.document.page_count}")
        first = self.document[0].rect
        print(f"Sayfa boyutu (pt): {first.width:.1f} x {first.height:.1f}")
        for key, value in (self.document.metadata or {}).items():
            if value:
                print(f"  {key}: {value}")

    def text(self, pages):
        for number in _page_range(pages, self.document.page_count):
            print(f"===== PDF sayfa {number} =====")
            print(self.document[number - 1].get_text())

    def layout(self, number):
        page = self.document[int(number) - 1]
        lines = _lines(page)
        for line in lines:
            print(_line_row(line, page.rect.height))
        print("\nFont / boyut / karakter sayısı:")
        for (font, size), count in _font_usage(lines).most_common():
            print(f"  {font:28} {size:5.1f}  {count}")

    def offset(self, first, last):
        votes, examples = self._offset_votes(first, last)
        if not votes:
            print("Basılı sayfa numarası bulunamadı; ofseti elle belirleyin.")
            return
        print("Olası ofsetler (PDF sayfası - kitap sayfası):")
        for offset, count in votes.most_common(TOP_CANDIDATES):
            pdf_page, folio = examples[offset]
            print(f"  offset={offset:4}  {count:4} oy   örnek: PDF {pdf_page} = kitap {folio}")

    def _offset_votes(self, first, last):
        votes, examples = Counter(), {}
        for number, folio in self._folios(first, last):
            offset = number - folio
            if offset >= 0:
                votes[offset] += 1
                examples.setdefault(offset, (number, folio))
        return votes, examples

    def _folios(self, first, last):
        """(PDF sayfası, basılı sayfa numarası) adayları."""
        numbers = range(first, min(last, self.document.page_count) + 1)
        return [(number, folio) for number in numbers for folio in _folio_candidates(_lines(self.document[number - 1]))]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info").set_defaults(run=lambda inspector, args: inspector.info())
    text = commands.add_parser("text")
    text.add_argument("pages", help="örn. 5 veya 5-9 (PDF sayfaları)")
    text.set_defaults(run=lambda inspector, args: inspector.text(args.pages))
    layout = commands.add_parser("layout")
    layout.add_argument("page", help="PDF sayfası")
    layout.set_defaults(run=lambda inspector, args: inspector.layout(args.page))
    offset = commands.add_parser("offset")
    offset.add_argument("--from", dest="first", type=int, default=1)
    offset.add_argument("--to", dest="last", type=int, default=400)
    offset.set_defaults(run=lambda inspector, args: inspector.offset(args.first, args.last))
    return parser.parse_args()


def main():
    args = parse_args()
    with fitz.open(args.pdf) as document:
        args.run(PdfInspector(document), args)


if __name__ == "__main__":
    main()
