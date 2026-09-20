"""Yeni bir kitap çeviri projesi kurar: okuyucu iskeleti, progress.json,
glossary.md, CLAUDE.md. PDF proje içine book.pdf olarak kopyalanır (git'e girmez).

Kullanım:
  python3 init_book.py --pdf /yol/kitap.pdf --title "Kitap Adı" --author "Yazar" \
      --offset 31 --total 431 [--subtitle "..."] [--subtitle-tr "..."] [--series "..."] \
      [--slug kitap-adi] [--chapters chapters.json] [--code-lang java] \
      [--pages-per-run 3] [--target DIR]

chapters.json: [{"num": 1, "en": "...", "tr": "...", "start": 1}, ...]
Hedef dizinde zaten progress.json varsa durur (üzerine yazmaz).
"""
import argparse
import json
import os
import re
import shutil

import fitz

from project import PROGRESS_FILE, Project
from toc_builder import rebuild

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates", "project")
PDF_NAME = "book.pdf"
DEFAULT_PAGES_PER_RUN = 3
DEFAULT_CODE_LANGUAGE = "java"
PLACEHOLDER_FILES = ("CLAUDE.md", "index.html", "glossary.md")


def slugify(title):
    ascii_title = title.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-") or "kitap"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--offset", type=int, required=True, help="PDF sayfası - kitap sayfası")
    parser.add_argument("--total", type=int, required=True, help="kitabın son sayfa numarası")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--subtitle-tr", default="")
    parser.add_argument("--series", default="")
    parser.add_argument("--slug", default="")
    parser.add_argument("--chapters", help="bölüm tablosu JSON dosyası")
    parser.add_argument("--code-lang", default=DEFAULT_CODE_LANGUAGE)
    parser.add_argument("--pages-per-run", type=int, default=DEFAULT_PAGES_PER_RUN)
    parser.add_argument("--target", default=os.getcwd())
    return parser.parse_args()


def ensure_empty_target(target):
    os.makedirs(target, exist_ok=True)
    if os.path.exists(os.path.join(target, PROGRESS_FILE)):
        raise SystemExit(f"{target} zaten bir kitap projesi ({PROGRESS_FILE} var); durduruldu.")


def copy_skeleton(target):
    shutil.copytree(TEMPLATE_DIR, target, dirs_exist_ok=True)


def fill_placeholders(target, mapping):
    for name in PLACEHOLDER_FILES:
        path = os.path.join(target, name)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for key, value in mapping.items():
            text = text.replace("{{" + key + "}}", value)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)


def place_pdf(source, target):
    """PDF'i projeye kopyalar; zaten proje içindeyse yalnız göreli adını verir."""
    source = os.path.abspath(source)
    if os.path.commonpath([source, os.path.abspath(target)]) == os.path.abspath(target):
        return os.path.relpath(source, target)
    shutil.copy2(source, os.path.join(target, PDF_NAME))
    return PDF_NAME


def pdf_page_count(path):
    document = fitz.open(path)
    try:
        return document.page_count
    finally:
        document.close()


def load_chapters(path):
    if not path:
        return []
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def build_progress(args, pdf_name, pdf_total, chapters):
    return {
        "book": {"slug": args.slug or slugify(args.title), "title": args.title,
                 "subtitle": args.subtitle, "subtitle_tr": args.subtitle_tr,
                 "author": args.author, "series": args.series},
        "book_pdf": pdf_name,
        "pdf_offset": args.offset,
        "book_total_pages": args.total,
        "pdf_total_pages": pdf_total,
        "pages_per_run": args.pages_per_run,
        "translator": {"vision": True},
        "extraction": {"default_code_language": args.code_lang},
        "last_translated_page": 0,
        "chapters": chapters,
        "pages": {},
    }


def report(project, progress):
    print(f"✓ Kitap projesi kuruldu: {project.root}")
    print(f"  kitap: {progress['book']['title']} — {progress['book']['author']}")
    print(f"  PDF: {progress['book_pdf']} ({progress['pdf_total_pages']} sayfa), "
          f"ofset {progress['pdf_offset']}, kitap {progress['book_total_pages']} sayfa")
    print(f"  bölüm sayısı: {len(progress['chapters'])}")
    print("\nSonraki adımlar:")
    print("  - Bölüm tablosu boşsa progress.json -> chapters alanını doldurun (init'ten sonra tek seferlik).")
    print("  - Kod fontu/başlık boyutları farklıysa: inspect_pdf.py <pdf> layout N ile bakıp "
          "progress.json -> extraction ayarlarını düzeltin.")
    print("  - Okuyucu: python3 -m http.server 8000  →  http://localhost:8000")
    print("  - İlk sayfa: /kitap-cevir 1  (ya da 'sıradaki sayfa')")


def main():
    args = parse_args()
    target = os.path.abspath(args.target)
    ensure_empty_target(target)
    copy_skeleton(target)
    fill_placeholders(target, {"TITLE": args.title, "AUTHOR": args.author})
    pdf_name = place_pdf(args.pdf, target)
    pdf_total = pdf_page_count(os.path.join(target, pdf_name))
    progress = build_progress(args, pdf_name, pdf_total, load_chapters(args.chapters))
    project = Project(target)
    project.save_progress(progress)
    rebuild(project)
    report(project, progress)


if __name__ == "__main__":
    main()
