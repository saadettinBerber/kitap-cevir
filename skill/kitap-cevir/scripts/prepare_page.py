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

import fitz

from extraction.page_extractor import PageExtractor
from extraction.text_utils import normalize_spaces
from page_document import PageDocument
from project import (Project, concepts_settings, extraction_settings,
                     translator_has_vision)

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


def _page_text(document, pdf_page):
    """İlk sayfanın öncesi ve son sayfanın sonrası boş metindir."""
    if not 1 <= pdf_page <= document.page_count:
        return ""
    return normalize_spaces(document[pdf_page - 1].get_text())


def context_snippets(document, pdf_page):
    return {"prev_tail": _page_text(document, pdf_page - 1)[-CONTEXT_CHARS:],
            "next_head": _page_text(document, pdf_page + 1)[:CONTEXT_CHARS]}


class PagePreparer:
    """Bir projenin sayfalarını çevirmen girdisine dönüştürür."""

    def __init__(self, project, progress, extractor):
        self.project = project
        self.progress = progress
        self.extractor = extractor
        self.pdf = project.pdf_path(progress)

    @classmethod
    def for_project(cls, project):
        progress = project.load_progress()
        return cls(project, progress, PageExtractor(extraction_settings(progress)))

    def hyphen_fixes(self, pdf_page):
        return self.extractor.hyphen_fixes(self.pdf, pdf_page)

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
            "concepts": [], "concepts_spec": concepts_settings(self.progress),
            "glossary_new": [],
            "context": self._context(pdf_page),
        }

    def _context(self, pdf_page):
        with fitz.open(self.pdf) as document:
            return context_snippets(document, pdf_page)

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
        page_document = PageDocument(document)
        if page_document.is_blank():
            print(f"  ! Sayfa {page} boş" + (" — atlandı, işaretlendi" if auto_skip else ""))
            if auto_skip:
                self.mark_blank(page)
            return None
        return {"page": page, "pdf_page": document["pdf_page"],
                "path": self.project.relative(self.write_input(document)),
                "blocks": page_document.block_summary(), "math": page_document.equation_count()}


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


def _report(prepared, has_vision, concepts):
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Hazırlanan sayfa sayısı: {len(prepared)}")
    print(f"kart türleri: {', '.join(concepts['kinds'])} (tür karta göre seçilir); "
          f"kod dilleri {', '.join(concepts['code_langs'])}, kod yorumları {concepts['code_comment_lang']}\n")
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
    preparer = PagePreparer.for_project(Project())
    prepared = [p for p in preparer.prepare_pages(spec, count) if p]
    if not prepared:
        print("Hazırlanacak sayfa yok.")
        return
    _report(prepared, translator_has_vision(preparer.progress),
            concepts_settings(preparer.progress))


if __name__ == "__main__":
    main()
