"""Sıradaki (ya da belirtilen) kitap sayfasını PDF'ten çıkarır ve çevirmen
agent'ının girdi dosyasını üretir: <proje>/_work/in/page-N.json

Kullanım (proje dizininde):
  python3 prepare_page.py             -> progress.json'daki sıradaki sayfa(lar)
  python3 prepare_page.py 55          -> yalnız kitap sayfası 55
  python3 prepare_page.py next --count 3

Boş sayfalar (bölüm sonu) "next" akışında otomatik atlanır ve progress.json'da
blank olarak işaretlenir. Görseller _work/in/page-N_images/ altına yazılır.
"""
import os
import sys

from json_file import write_json
from page_document import PageDocument
from page_input import PageInputBuilder
from project import Project, translator_has_vision

MAX_BLANK_SKIPS = 3
NEXT_ALIASES = ("next", "sıradaki", "sonraki", "devam")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


class PagePreparer:
    """Sıradaki ya da istenen sayfaların girdisini yazar; boş sayfaları ilerlemeye işler."""

    def __init__(self, project, progress, builder):
        self.project = project
        self.progress = progress
        self.builder = builder

    @classmethod
    def for_project(cls, project):
        progress = project.load_progress()
        return cls(project, progress, PageInputBuilder.for_progress(project, progress))

    def write_input(self, document):
        return write_json(self.project.work_input(document["page"]), document)

    def mark_blank(self, page):
        self.progress["pages"][str(page)] = {"blank": True, "pdf_page": self.builder.pdf_page(page)}
        self.progress["last_translated_page"] = max(self.progress["last_translated_page"], page)
        self.project.save_progress(self.progress)

    def prepare_pages(self, spec, count):
        """Hazırlanan sayfaların özetleri; boş sayfa özet üretmez."""
        if spec not in NEXT_ALIASES:
            return self._prepare_requested(int(spec))
        wanted = count or self.progress.get("pages_per_run", 1)
        prepared = []
        for page in self._candidate_pages(wanted + MAX_BLANK_SKIPS):
            if len(prepared) < wanted:
                prepared += self._prepare_next(page)
        return prepared

    def _candidate_pages(self, count):
        start = self.progress["last_translated_page"] + 1
        end = min(start + count - 1, self.progress["book_total_pages"])
        return list(range(start, end + 1))

    def _prepare_requested(self, page):
        prepared = self._prepare(page)
        if not prepared:
            print(f"  ! Sayfa {page} boş")
        return prepared

    def _prepare_next(self, page):
        """Sıradaki akışta boş sayfa (bölüm sonu) atlanır ve işaretlenir."""
        prepared = self._prepare(page)
        if not prepared:
            print(f"  ! Sayfa {page} boş — atlandı, işaretlendi")
            self.mark_blank(page)
        return prepared

    def _prepare(self, page):
        page_document = PageDocument(self.builder.build(page))
        if page_document.is_blank():
            return []
        document = page_document.data
        return [{"page": page, "pdf_page": document["pdf_page"],
                 "path": self.project.relative(self.write_input(document)),
                 "blocks": page_document.block_summary(), "math": page_document.equation_count()}]


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


def _print_entry(entry, has_vision):
    print(f"  Sayfa {entry['page']} (PDF {entry['pdf_page']})  [{entry['blocks']}]")
    print(f"    girdi: {entry['path']}")
    if entry["math"]:
        print(f"    denklem: {entry['math']} PNG — {_math_note(has_vision)}")


def _report(prepared, progress):
    print(f"Hazırlanan sayfa sayısı: {len(prepared)}\n")
    for entry in prepared:
        _print_entry(entry, translator_has_vision(progress))
    print("\nSonraki adım: her girdi için bir çevirmen agent çalıştır "
          "(sözleşme: references/FORMAT.md), çıktıyı _work/out/page-N.json yaz, "
          f"sonra: python3 {SCRIPTS_DIR}/finalize_page.py _work/out/page-N.json; "
          "kartlar en son (SKILL.md → C)")


def main():
    spec, count = parse_args(sys.argv)
    preparer = PagePreparer.for_project(Project())
    prepared = preparer.prepare_pages(spec, count)
    if not prepared:
        print("Hazırlanacak sayfa yok.")
        return
    _report(prepared, preparer.progress)


if __name__ == "__main__":
    main()
