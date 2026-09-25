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
from project import Project

MAX_BLANK_SKIPS = 3
NEXT_ALIASES = ("next", "sıradaki", "sonraki", "devam")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


class PagePreparer:
    """Sayfaların çevirmen girdisini _work/in'e yazar."""

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
        self.progress.mark_blank(page)
        self.project.save_progress(self.progress)

    def prepare_next(self, count):
        """(hazırlanan sayfaların özetleri, atlanan boş sayfalar). Sıradaki akışta
        boş sayfa (bölüm sonu) işaretlenir ki sonraki çalıştırma onu geçsin."""
        wanted = count or self.progress.pages_per_run()
        prepared, blanks = [], []
        for page in self.progress.next_pages(wanted + MAX_BLANK_SKIPS):
            if len(prepared) == wanted:
                break
            entry = self._prepare(page)
            if not entry:
                self.mark_blank(page)
                blanks.append(page)
            prepared += entry
        return prepared, blanks

    def prepare_page(self, page):
        """İstenen sayfanın özeti; boşsa boş liste, işaretlenmez."""
        return self._prepare(page)

    def _prepare(self, page):
        page_document = PageDocument(self.builder.build(page, self.project.work_images(page)))
        if page_document.is_blank():
            return []
        document = page_document.data
        return [{"page": page, "pdf_page": document["pdf_page"],
                 "path": self.project.relative_to_root(self.write_input(document)),
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


def _report(prepared, settings):
    print(f"Hazırlanan sayfa sayısı: {len(prepared)}\n")
    for entry in prepared:
        _print_entry(entry, settings.translator_has_vision())
    print("\nSonraki adım: her girdi için bir çevirmen agent çalıştır "
          "(sözleşme: references/FORMAT.md), çıktıyı _work/out/page-N.json yaz, "
          f"sonra: python3 {SCRIPTS_DIR}/finalize_page.py _work/out/page-N.json; "
          "kartlar en son (SKILL.md → C)")


def _prepare(preparer, spec, count):
    if spec not in NEXT_ALIASES:
        prepared = preparer.prepare_page(int(spec))
        if not prepared:
            print(f"  ! Sayfa {spec} boş")
        return prepared
    prepared, blanks = preparer.prepare_next(count)
    for page in blanks:
        print(f"  ! Sayfa {page} boş — atlandı, işaretlendi")
    return prepared


def main():
    spec, count = parse_args(sys.argv)
    project = Project.discover()
    prepared = _prepare(PagePreparer.for_project(project), spec, count)
    if not prepared:
        print("Hazırlanacak sayfa yok.")
        return
    _report(prepared, project.load_settings())


if __name__ == "__main__":
    main()
