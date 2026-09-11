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
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if spans:
                lines.append({"bbox": line["bbox"], "spans": spans,
                              "text": "".join(s["text"] for s in spans).strip()})
    lines.sort(key=lambda ln: (round(ln["bbox"][1]), ln["bbox"][0]))
    return lines


def show_info(document, _args):
    print(f"PDF sayfa sayısı: {document.page_count}")
    first = document[0].rect
    print(f"Sayfa boyutu (pt): {first.width:.1f} x {first.height:.1f}")
    for key, value in (document.metadata or {}).items():
        if value:
            print(f"  {key}: {value}")


def show_text(document, args):
    for number in _page_range(args.pages, document.page_count):
        print(f"===== PDF sayfa {number} =====")
        print(document[number - 1].get_text())


def _line_row(line, height):
    span = line["spans"][0]
    odl_y = height - line["bbox"][3]
    return (f"y={line['bbox'][1]:6.1f}  odlY={odl_y:6.1f}  size={span['size']:5.2f}  "
            f"{span['font'][:22]:22}  {line['text'][:TEXT_PREVIEW_CHARS]}")


def show_layout(document, args):
    page = document[int(args.page) - 1]
    height = page.rect.height
    fonts = Counter()
    for line in _lines(page):
        print(_line_row(line, height))
        for span in line["spans"]:
            fonts[(span["font"], round(span["size"], 1))] += len(span["text"])
    print("\nFont / boyut / karakter sayısı:")
    for (font, size), count in fonts.most_common():
        print(f"  {font:28} {size:5.1f}  {count}")


def _folio_candidates(lines):
    edge = lines[:EDGE_LINES] + lines[-EDGE_LINES:]
    for line in edge:
        match = _EDGE_NUMBER.search(line["text"])
        if match:
            number = int(match.group(1) or match.group(2))
            if 0 < number <= MAX_FOLIO:
                yield number


def _offset_votes(document, first, last):
    votes, examples = Counter(), {}
    for number in range(first, min(last, document.page_count) + 1):
        for folio in _folio_candidates(_lines(document[number - 1])):
            offset = number - folio
            if offset >= 0:
                votes[offset] += 1
                examples.setdefault(offset, (number, folio))
    return votes, examples


def show_offset(document, args):
    votes, examples = _offset_votes(document, args.first, args.last)
    if not votes:
        print("Basılı sayfa numarası bulunamadı; ofseti elle belirleyin.")
        return
    print("Olası ofsetler (PDF sayfası - kitap sayfası):")
    for offset, count in votes.most_common(TOP_CANDIDATES):
        pdf_page, folio = examples[offset]
        print(f"  offset={offset:4}  {count:4} oy   örnek: PDF {pdf_page} = kitap {folio}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info").set_defaults(run=show_info)
    text = commands.add_parser("text")
    text.add_argument("pages", help="örn. 5 veya 5-9 (PDF sayfaları)")
    text.set_defaults(run=show_text)
    layout = commands.add_parser("layout")
    layout.add_argument("page", help="PDF sayfası")
    layout.set_defaults(run=show_layout)
    offset = commands.add_parser("offset")
    offset.add_argument("--from", dest="first", type=int, default=1)
    offset.add_argument("--to", dest="last", type=int, default=400)
    offset.set_defaults(run=show_offset)
    return parser.parse_args()


def main():
    args = parse_args()
    document = fitz.open(args.pdf)
    try:
        args.run(document, args)
    finally:
        document.close()


if __name__ == "__main__":
    main()
