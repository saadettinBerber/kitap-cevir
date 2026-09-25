"""Çevrilmiş sayfaları yeni çıkarım yapısına taşır (yeniden çeviri yok).

  python3 migrate_page.py 5 13 121        -> sayfaları yeniden çıkarır, eski
      çevirileri yeni yapıya aktarır, _work/out/page-N.json yazar; eşleşmeyen
      birimler _work/migrate/pending-N.json'a düşer. Eksiksiz sayfalar hemen
      sonlandırılır (--no-finalize ile ertelenir).
  python3 migrate_page.py all              -> progress.json'da kayıtlı tüm çevrilmiş sayfalar
  python3 migrate_page.py apply 13 31      -> _work/migrate/done-N.json içindeki
      çevirileri ({path, tr} ve {src, latex}) uygulayıp sonlandırır.
"""
import os
import re
import sys

from finalize_page import PageFinalizer
from json_file import read_json, write_json
from migrate_match import TranslationFiller, Translations
from page_document import PageDocument
from page_input import PageInputBuilder
from project import Project
from translated_pages import TranslatedPages

_COPY_FIELDS = ("title", "section", "concepts")
_PATH_STEP = re.compile(r"(\w+)|\[(\d+)\]")


class PageMigration:
    """Yeni çıkarılmış sayfa girdisine eski sayfanın çevirilerini, başlıklarını,
    kartlarını ve denklem LaTeX'ini taşır."""

    def __init__(self, document, old):
        self.document = document
        self.old = old

    def run(self, fixes):
        """(pending, latex_items): çevirisi bulunamayan birimler ve LaTeX'i olmayan denklemler."""
        filler = TranslationFiller(Translations.of_page(self.old, fixes))
        for index, block in enumerate(self.document["blocks"]):
            filler.fill_block(block, f"blocks[{index}]")
        for field in _COPY_FIELDS:
            self.document[field] = self.old.get(field, self.document.get(field))
        self._carry_latex()
        if not self.document.get("chapter", {}).get("tr"):
            self.document["chapter"] = self.old.get("chapter", self.document["chapter"])
        self.document["glossary_new"] = []
        return filler.pending, self._missing_latex()

    def _carry_latex(self):
        """Eski sayfada aynı PNG için LaTeX yazılmışsa yeni yapıya taşınır; ayrı
        satır denkleminin LaTeX'i satır içindekinden önceliklidir."""
        old, new = PageDocument(self.old), PageDocument(self.document)
        known = {item["src"]: item.get("latex", "") for item in old.inline_math() + old.display_math()}
        for item in new.display_math() + new.inline_math():
            item["latex"] = item.get("latex") or known.get(item["src"], "")

    def _missing_latex(self):
        page = PageDocument(self.document)
        blocks = [{"path": f"blocks[{i}]", "src": equation["src"]} for i, block in enumerate(page.blocks())
                  for equation in block.equations() if not equation["latex"]]
        return blocks + [{"path": f"math[{i}]", "src": m["src"]}
                         for i, m in enumerate(page.inline_math()) if not m["latex"]]


class Migrator:
    """Projenin çevrilmiş sayfalarını taşır; bekleyenleri _work/migrate'e yazar."""

    def __init__(self, project, builder, finalizer):
        self.project = project
        self.pages = TranslatedPages(project)
        self.builder = builder
        self.finalizer = finalizer

    @classmethod
    def for_project(cls, project):
        return cls(project, PageInputBuilder.for_progress(project, project.load_progress()), PageFinalizer.for_project(project))

    def run(self, page):
        """Sayfayı yeniden çıkarıp eski çevirileri taşır; sonlandırmaz."""
        old = self.pages.get(page).data
        document = self.builder.build(page)
        pending, latex_items = PageMigration(document, old).run(self.builder.hyphen_fixes(document["pdf_page"]))
        write_json(self._out_path(page), document)
        self._write_pending(page, pending, latex_items)
        return {"page": page, "units": len(PageDocument(document).text_units()), "pending": len(pending),
                "latex": len(latex_items), "complete": not pending and not latex_items}

    def finalize(self, page):
        return self.finalizer.finalize(self._out_path(page))

    def apply(self, page):
        """done-N.json'daki çevirileri ({path, tr} ve {path, latex}) yazar ve sonlandırır."""
        done = read_json(self.project.work_migration_file("done", page))
        document = read_json(self._out_path(page))
        for item in done.get("units", []):
            self._resolve(document, item["path"])["tr"] = item["tr"]
        for item in done.get("latex", []):
            self._resolve(document, item["path"])["latex"] = item["latex"]
        write_json(self._out_path(page), document)
        return self.finalize(page)

    def _out_path(self, page):
        return self.project.work_output(page)

    def _write_pending(self, page, pending, latex_items):
        path = self.project.work_migration_file("pending", page)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if pending or latex_items:
            write_json(path, {"page": page, "units": pending, "latex": latex_items})
        elif os.path.exists(path):
            os.remove(path)

    @staticmethod
    def _resolve(document, path):
        """'blocks[3].sentences[1]' gibi bir yolun gösterdiği birim."""
        node = document
        for key, index in _PATH_STEP.findall(path):
            node = node[key] if key else node[int(index)]
        return node



def _apply_done(migrator, pages):
    for page in pages:
        result = migrator.apply(int(page))
        print(f"✓ sayfa {page} uygulandı ve sonlandırıldı (boş tr: {result['untranslated']})")


def _status(result):
    if result["finalized"]:
        return "sonlandırıldı"
    return f"bekliyor (pending {result['pending']}, latex {result['latex']})"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    project = Project.discover()
    migrator = Migrator.for_project(project)
    if args[:1] == ["apply"]:
        _apply_done(migrator, args[1:])
        return
    finalizes_complete = "--no-finalize" not in sys.argv
    for page in project.load_progress().translated_pages() if args == ["all"] else [int(a) for a in args]:
        result = migrator.run(page)
        result["finalized"] = result["complete"] and finalizes_complete
        if result["finalized"]:
            migrator.finalize(page)
        print(f"sayfa {result['page']}: {result['units']} birim, {_status(result)}")


if __name__ == "__main__":
    main()
