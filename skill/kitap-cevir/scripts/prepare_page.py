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
NEXT_STEP = ("\nSonraki adım: her girdi için bir çevirmen agent çalıştır "
             "(sözleşme: references/FORMAT.md), çıktıyı _work/out/page-N.json yaz, "
             f"sonra: python3 {SCRIPTS_DIR}/finalize_page.py _work/out/page-N.json; "
             "kartlar en son (SKILL.md → C)")


class PagePreparer:
    """Sayfaların çevirmen girdisini _work/in'e yazar."""

    def __init__(self, project, builder):
        self._project = project
        self._builder = builder

    @classmethod
    def for_project(cls, project):
        return cls(project, PageInputBuilder.for_progress(project, project.load_progress()))

    def prepare_next(self, count):
        """(hazırlanan sayfaların özetleri, atlanan boş sayfalar). Sıradaki akışta
        boş sayfa (bölüm sonu) işaretlenir ki sonraki çalıştırma onu geçsin."""
        progress = self._project.load_progress()
        wanted = count or progress.pages_per_run()
        prepared, blanks = [], []
        for page in progress.next_pages(wanted + MAX_BLANK_SKIPS):
            if len(prepared) == wanted:
                break
            entry = self._prepare(page)
            if not entry:
                self._mark_blank(progress, page)
                blanks.append(page)
            prepared += entry
        return prepared, blanks

    def prepare_page(self, page):
        """İstenen sayfanın özeti; boşsa boş liste, işaretlenmez."""
        return self._prepare(page)

    def _prepare(self, page):
        page_document = PageDocument(self._builder.build(page, self._project.work_images(page)))
        if page_document.is_blank():
            return []
        path = write_json(self._project.work_input(page), page_document.data)
        return [{"page": page, "pdf_page": page_document.data["pdf_page"], "path": self._project.relative_to_root(path),
                 "blocks": page_document.block_summary(), "math": page_document.equation_count()}]

    def _mark_blank(self, progress, page):
        progress.mark_blank(page)
        self._project.save_progress(progress)


def parse_args(argv):
    spec, count = "next", None
    args = list(argv[1:])
    if "--count" in args:
        count = int(args[args.index("--count") + 1])
        del args[args.index("--count"):args.index("--count") + 2]
    if args:
        spec = args[0]
    return spec, count


class PreparationReport:
    """Hazırlanan girdilerin kullanıcıya özeti; denklem notu çevirmenin görsel okuyup
    okuyamadığına bağlıdır."""

    def __init__(self, has_vision):
        self._has_vision = has_vision

    def show(self, prepared):
        if not prepared:
            print("Hazırlanacak sayfa yok.")
            return
        print(f"Hazırlanan sayfa sayısı: {len(prepared)}\n")
        for entry in prepared:
            self._print_entry(entry)
        print(NEXT_STEP)

    def _print_entry(self, entry):
        print(f"  Sayfa {entry['page']} (PDF {entry['pdf_page']})  [{entry['blocks']}]")
        print(f"    girdi: {entry['path']}")
        if entry["math"]:
            print(f"    denklem: {entry['math']} PNG — {self._math_note()}")

    def _math_note(self):
        if self._has_vision:
            return "çevirmen PNG'leri okuyup `latex` alanlarını doldursun"
        return "translator.vision=false: `latex` boş kalır, okuyucu PNG gösterir"


def _prepare_one(preparer, spec):
    prepared = preparer.prepare_page(int(spec))
    if not prepared:
        print(f"  ! Sayfa {spec} boş")
    return prepared


def _prepare_next(preparer, count):
    prepared, blanks = preparer.prepare_next(count)
    for page in blanks:
        print(f"  ! Sayfa {page} boş — atlandı, işaretlendi")
    return prepared


def main():
    spec, count = parse_args(sys.argv)
    project = Project.discover()
    preparer = PagePreparer.for_project(project)
    prepared = _prepare_next(preparer, count) if spec in NEXT_ALIASES else _prepare_one(preparer, spec)
    settings = project.load_settings()
    PreparationReport(settings.translator_has_vision()).show(prepared)


if __name__ == "__main__":
    main()
