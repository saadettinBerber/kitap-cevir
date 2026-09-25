"""Yeni bir kitap çeviri projesi kurar: okuyucu iskeleti, progress.json,
glossary.md, CLAUDE.md. PDF proje içine book.pdf olarak kopyalanır (git'e girmez).

Kullanım:
  python3 init_book.py --pdf /yol/kitap.pdf --title "Kitap Adı" --author "Yazar" \
      --offset 31 --total 431 [--subtitle "..."] [--subtitle-tr "..."] [--series "..."] \
      [--slug kitap-adi] [--chapters chapters.json] [--code-lang java] \
      [--card-kinds explain,contrast,tradeoff,code] [--pages-per-run 3] [--target DIR]

--card-kinds: bu kitapta izinli kavram kartı türleri (virgülle). Çevirmen her
kart için konuya uyan türü bu listeden seçer: `explain` tanım + ipucu,
`contrast` kaçın/tercih et karşıtlığı (metin), `tradeoff` seçeneklerin kazanç ve
bedeli, `code` önce/sonra kod çifti. Varsayılan: hepsi. Ayrıntı: references/FORMAT.md.

chapters.json: [{"num": 1, "en": "...", "tr": "...", "start": 1}, ...]
Hedef dizinde zaten progress.json varsa durur (üzerine yazmaz).
"""
import argparse
import os
import re
import shutil

from book_settings import CARD_KINDS, DEFAULT_CODE_COMMENT_LANG
from extraction.pdf.pymupdf_adapter import PyMuPdfDocument
from json_file import read_json
from progress import Progress
from project import PROGRESS_FILE, Project
from reader_data import ReaderData

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates", "project")
PDF_NAME = "book.pdf"
DEFAULT_PAGES_PER_RUN = 3
DEFAULT_CODE_LANGUAGE = "java"
PLACEHOLDER_FILES = ("CLAUDE.md", "index.html", "glossary.md")
NEXT_STEPS = (
    "\nSonraki adımlar:\n"
    "  - Kart türleri kitaba uymuyorsa progress.json -> concepts.kinds listesini daraltın "
    "(ör. kod zanaatı: code, contrast, explain; mimari: tradeoff, contrast, explain).\n"
    "  - Bölüm tablosu boşsa progress.json -> chapters alanını doldurun (init'ten sonra tek seferlik).\n"
    "  - Kod fontu/başlık boyutları farklıysa: inspect_pdf.py <pdf> layout N ile bakıp "
    "progress.json -> extraction ayarlarını düzeltin.\n"
    "  - Okuyucu: python3 -m http.server 8000  →  http://localhost:8000\n"
    "  - İlk sayfa: /kitap-cevir 1  (ya da 'sıradaki sayfa')")


def slugify(title):
    ascii_title = title.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-") or "kitap"


def card_kinds(text):
    kinds = [kind.strip() for kind in text.split(",") if kind.strip()]
    unknown = [kind for kind in kinds if kind not in CARD_KINDS]
    if unknown or not kinds:
        raise argparse.ArgumentTypeError(
            f"geçersiz kart türü: {', '.join(unknown) or repr(text)}; geçerli: {', '.join(CARD_KINDS)}")
    return kinds


def parse_args(argv=None):
    """argv verilmezse komut satırı (sys.argv) okunur."""
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
    parser.add_argument("--card-kinds", type=card_kinds, default=",".join(CARD_KINDS),
                        help="izinli kavram kartı türleri, virgülle (references/FORMAT.md)")
    parser.add_argument("--pages-per-run", type=int, default=DEFAULT_PAGES_PER_RUN)
    parser.add_argument("--target", default=os.getcwd())
    return parser.parse_args(argv)


class BookSetup:
    """Komut satırı seçeneklerinden yeni bir kitap projesi kurar; open_pdf: yol → PdfDocument."""

    def __init__(self, args, open_pdf):
        self._args = args
        self._target = os.path.abspath(args.target)
        self._open_pdf = open_pdf

    def run(self):
        self._ensure_empty_target()
        shutil.copytree(TEMPLATE_DIR, self._target, dirs_exist_ok=True)
        self._fill_placeholders({"TITLE": self._args.title, "AUTHOR": self._args.author})
        project = Project(self._target)
        project.save_progress(Progress(self._progress(self._place_pdf())))
        ReaderData(project).rebuild()
        return project

    def _ensure_empty_target(self):
        os.makedirs(self._target, exist_ok=True)
        if os.path.exists(os.path.join(self._target, PROGRESS_FILE)):
            raise SystemExit(f"{self._target} zaten bir kitap projesi ({PROGRESS_FILE} var); durduruldu.")

    def _fill_placeholders(self, mapping):
        for name in PLACEHOLDER_FILES:
            path = os.path.join(self._target, name)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            for key, value in mapping.items():
                text = text.replace("{{" + key + "}}", value)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)

    def _place_pdf(self):
        """PDF'i projeye kopyalar; zaten proje içindeyse yalnız göreli adını verir."""
        source = os.path.abspath(self._args.pdf)
        if os.path.commonpath([source, self._target]) == self._target:
            return os.path.relpath(source, self._target)
        shutil.copy2(source, os.path.join(self._target, PDF_NAME))
        return PDF_NAME

    def _progress(self, pdf_name):
        args = self._args
        return {"book": self._book(), "book_pdf": pdf_name, "pdf_offset": args.offset,
                "book_total_pages": args.total, "pdf_total_pages": self._page_count(pdf_name),
                "pages_per_run": args.pages_per_run, "translator": {"vision": True},
                "concepts": {"kinds": args.card_kinds, "code_comment_lang": DEFAULT_CODE_COMMENT_LANG},
                "extraction": {"default_code_language": args.code_lang},
                "last_translated_page": 0, "chapters": self._chapters(), "pages": {}}

    def _book(self):
        args = self._args
        return {"slug": args.slug or slugify(args.title), "title": args.title, "subtitle": args.subtitle,
                "subtitle_tr": args.subtitle_tr, "author": args.author, "series": args.series}

    def _page_count(self, pdf_name):
        with self._open_pdf(os.path.join(self._target, pdf_name)) as document:
            return document.page_count

    def _chapters(self):
        if not self._args.chapters:
            return []
        return read_json(self._args.chapters)


def report(root, project):
    print(f"✓ Kitap projesi kuruldu: {root}")
    progress = project.load_progress()
    settings, data = project.load_settings(), progress.as_json()
    book = settings.book()
    print(f"  kitap: {book['title']} — {book['author']}")
    print(f"  PDF: {settings.book_pdf()} ({data['pdf_total_pages']} sayfa), "
          f"ofset {data['pdf_offset']}, kitap {data['book_total_pages']} sayfa")
    print(f"  bölüm sayısı: {len(data['chapters'])}")
    print(f"  kart türleri: {', '.join(settings.concepts()['kinds'])}")
    print(NEXT_STEPS)


def main():
    args = parse_args()
    report(os.path.abspath(args.target), BookSetup(args, PyMuPdfDocument.open).run())


if __name__ == "__main__":
    main()
