"""Sıradaki (ya da belirtilen) kitap sayfasını PDF'ten çıkarır ve çevirmen
agent'ının girdi dosyasını üretir: <proje>/_work/in/page-N.json

Kullanım (proje dizininde):
  python3 prepare_page.py             -> progress.json'daki sıradaki sayfa(lar)
  python3 prepare_page.py 55          -> yalnız kitap sayfası 55
  python3 prepare_page.py next --count 3

Boş sayfalar (bölüm sonu) "next" akışında otomatik atlanır ve progress.json'da
blank olarak işaretlenir. Görseller _work/in/page-N_images/ altına yazılır.
"""
import json
import os
import sys

from layout_scan import page_plain_text
from odl_extract import PageExtractor
from project import Project, extraction_settings, translator_has_vision
from text_utils import normalize_spaces

CONTEXT_CHARS = 700
MAX_BLANK_SKIPS = 3
NEXT_ALIASES = ("next", "sıradaki", "sonraki", "devam")
UNKNOWN_CHAPTER = {"num": 0, "en": "", "tr": ""}


def chapter_of(progress, page):
    current = None
    for chapter in progress["chapters"]:
        if chapter["start"] <= page:
            current = chapter
    if current is None:
        return dict(UNKNOWN_CHAPTER)
    return {"num": current["num"], "en": current["en"], "tr": current["tr"]}


def _previous_section(progress, page):
    previous = progress["pages"].get(str(page - 1), {})
    return {"en": previous.get("section_en", ""), "tr": previous.get("section_tr", "")}


def _section_of(progress, page, header):
    """Koşu başlığı yoksa bölüm açılış sayfasıdır (kesit yok); tek sayfa
    başlığı (Chapter ...) ise kesit önceki sayfadan devam eder."""
    if header is None:
        return {"en": "", "tr": ""}
    if not header["is_chapter"] and header["text"]:
        return {"en": header["text"], "tr": ""}
    return _previous_section(progress, page)


def _context_snippets(pdf, pdf_page):
    previous = normalize_spaces(page_plain_text(pdf, pdf_page - 1))
    following = normalize_spaces(page_plain_text(pdf, pdf_page + 1))
    return {"prev_tail": previous[-CONTEXT_CHARS:],
            "next_head": following[:CONTEXT_CHARS]}


class PagePreparer:
    """Bir projenin sayfalarını çevirmen girdisine dönüştürür."""

    def __init__(self, project):
        self.project = project
        self.progress = project.load_progress()
        self.extractor = PageExtractor(extraction_settings(self.progress))
        self.pdf = project.pdf_path(self.progress)

    def build_input(self, page):
        pdf_page = page + self.progress["pdf_offset"]
        image_dir = os.path.join(self.project.work_in, f"page-{page}_images")
        extracted = self.extractor.extract(self.pdf, pdf_page, image_dir)
        return {
            "id": f"page-{page}", "page": page, "pdf_page": pdf_page,
            "chapter": chapter_of(self.progress, page),
            "section": _section_of(self.progress, page, extracted["running_header"]),
            "title": {"en": "", "tr": ""},
            "blocks": extracted["blocks"],
            "math": extracted["math"],
            "concepts": [], "glossary_new": [],
            "context": _context_snippets(self.pdf, pdf_page),
        }

    def write_input(self, document):
        os.makedirs(self.project.work_in, exist_ok=True)
        path = os.path.join(self.project.work_in, f"{document['id']}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
        return path

    def mark_blank(self, page):
        self.progress["pages"][str(page)] = {
            "blank": True, "pdf_page": page + self.progress["pdf_offset"]}
        self.progress["last_translated_page"] = max(self.progress["last_translated_page"], page)
        self.project.save_progress(self.progress)

    def _candidate_pages(self, count):
        start = self.progress["last_translated_page"] + 1
        end = min(start + count - 1, self.progress["book_total_pages"])
        return list(range(start, end + 1))

    def prepare_pages(self, spec, count):
        if spec not in NEXT_ALIASES:
            return [self._prepare_one(int(spec), auto_skip=False)]
        wanted = count or self.progress.get("pages_per_run", 1)
        prepared = []
        for page in self._candidate_pages(wanted + MAX_BLANK_SKIPS):
            if len(prepared) == wanted:
                break
            entry = self._prepare_one(page, auto_skip=True)
            if entry:
                prepared.append(entry)
        return prepared

    def _prepare_one(self, page, auto_skip):
        document = self.build_input(page)
        if _is_blank(document):
            print(f"  ! Sayfa {page} boş" + (" — atlandı, işaretlendi" if auto_skip else ""))
            if auto_skip:
                self.mark_blank(page)
            return None
        return {"page": page, "pdf_page": document["pdf_page"],
                "path": self.project.relative(self.write_input(document)),
                "blocks": _block_summary(document), "math": _math_count(document)}


def _is_blank(document):
    return not any(b["type"] != "image" for b in document["blocks"])


def _math_count(document):
    display = sum(1 for b in document["blocks"] if b["type"] == "math")
    return display + len(document.get("math", []))


def _block_summary(document):
    counts = {}
    for block in document["blocks"]:
        counts[block["type"]] = counts.get(block["type"], 0) + 1
    return ", ".join(f"{k}:{v}" for k, v in counts.items())


def parse_args(argv):
    spec, count = "next", None
    args = list(argv[1:])
    if "--count" in args:
        count = int(args[args.index("--count") + 1])
        del args[args.index("--count"):args.index("--count") + 2]
    if args:
        spec = args[0]
    return spec, count


def _math_note(has_vision):
    if has_vision:
        return "çevirmen PNG'leri okuyup `latex` alanlarını doldursun"
    return "translator.vision=false: `latex` boş kalır, okuyucu PNG gösterir"


def _report(prepared, has_vision):
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Hazırlanan sayfa sayısı: {len(prepared)}\n")
    for entry in prepared:
        print(f"  Sayfa {entry['page']} (PDF {entry['pdf_page']})  [{entry['blocks']}]")
        print(f"    girdi: {entry['path']}")
        if entry["math"]:
            print(f"    denklem: {entry['math']} PNG — {_math_note(has_vision)}")
    print("\nSonraki adım: her girdi için bir çevirmen agent çalıştır "
          "(sözleşme: references/FORMAT.md), çıktıyı _work/out/page-N.json yaz, "
          f"sonra: python3 {scripts_dir}/finalize_page.py _work/out/page-N.json")


def main():
    spec, count = parse_args(sys.argv)
    preparer = PagePreparer(Project())
    prepared = [p for p in preparer.prepare_pages(spec, count) if p]
    if not prepared:
        print("Hazırlanacak sayfa yok.")
        return
    _report(prepared, translator_has_vision(preparer.progress))


if __name__ == "__main__":
    main()
