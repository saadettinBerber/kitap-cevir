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
FINALIZED = "sonlandırıldı"
_PATH_STEP = re.compile(r"(\w+)|\[(\d+)\]")


class PageMigration:
    """Yeni çıkarılmış sayfa girdisine eski sayfanın çevirilerini, başlıklarını,
    kartlarını ve denklem LaTeX'ini taşır."""

    def __init__(self, document, old):
        self._document = document
        self._old = old

    def run(self, fixes):
        """Bekleyenler: çevirisi bulunamayan birimler (units) ve LaTeX'i olmayan denklemler (latex)."""
        filler = TranslationFiller(Translations.of_page(self._old, fixes))
        for index, block in enumerate(self._document["blocks"]):
            filler.fill_block(block, f"blocks[{index}]")
        self._carry_fields()
        self._carry_latex()
        return {"units": filler.pending(), "latex": self._missing_latex()}

    def _carry_fields(self):
        """Başlık, kesit ve kartlar eski sayfadan gelir; bölümün Türkçesi yoksa bölüm de. Eski sayfanın
        terimleri sözlükte olduğundan yeni terim listesi boşalır."""
        for field in _COPY_FIELDS:
            self._document[field] = self._old.get(field, self._document.get(field))
        if not self._document.get("chapter", {}).get("tr"):
            self._document["chapter"] = self._old.get("chapter", self._document["chapter"])
        self._document["glossary_new"] = []

    def _carry_latex(self):
        """Eski sayfada aynı PNG için LaTeX yazılmışsa yeni yapıya taşınır; ayrı
        satır denkleminin LaTeX'i satır içindekinden önceliklidir."""
        old, new = PageDocument(self._old), PageDocument(self._document)
        known = {item["src"]: item.get("latex", "") for item in old.inline_math() + old.display_math()}
        for item in new.display_math() + new.inline_math():
            item["latex"] = item.get("latex") or known.get(item["src"], "")

    def _missing_latex(self):
        page = PageDocument(self._document)
        blocks = [{"path": f"blocks[{i}]", "src": equation["src"]} for i, block in enumerate(page.blocks())
                  for equation in block.equations() if not equation["latex"]]
        return blocks + [{"path": f"math[{i}]", "src": m["src"]}
                         for i, m in enumerate(page.inline_math()) if not m["latex"]]


class Migrator:
    """Projenin çevrilmiş sayfalarını yeni çıkarıma taşır; bekleyenleri _work/migrate'e yazar."""

    def __init__(self, project, builder):
        self._project = project
        self._pages = TranslatedPages(project)
        self._builder = builder

    @classmethod
    def for_progress(cls, project, progress):
        return cls(project, PageInputBuilder.for_progress(project, progress))

    def run(self, page):
        """Sayfayı yeniden çıkarıp eski çevirileri taşır; sonlandırmaz."""
        old = self._pages.get(page).data
        document = self._builder.build(page, self._project.work_images(page))
        pending = PageMigration(document, old).run(self._builder.hyphen_fixes(document["pdf_page"]))
        write_json(self._project.work_output(page), document)
        self._write_pending(page, pending)
        return {"page": page, **_summary(document, pending)}

    def _write_pending(self, page, pending):
        """Bekleyen yoksa eski bekleyenler dosyası da silinir: sayfa tamamlanmıştır."""
        path = self._project.work_migration_file("pending", page)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if pending["units"] or pending["latex"]:
            write_json(path, {"page": page, **pending})
        elif os.path.exists(path):
            os.remove(path)


class MigrationFinisher:
    """Taşınmış sayfayı sonlandırır; ajanın doldurduğu bekleyenler (done-N.json) önce yazılır."""

    def __init__(self, project, finalizer):
        self._project = project
        self._finalizer = finalizer

    @classmethod
    def for_project(cls, project):
        return cls(project, PageFinalizer.for_project(project))

    def finalize(self, page):
        return self._finalizer.finalize(self._project.work_output(page))

    def apply(self, page):
        """done-N.json'daki çevirileri ({path, tr} ve {path, latex}) yazar ve sonlandırır."""
        done = read_json(self._project.work_migration_file("done", page))
        document = read_json(self._project.work_output(page))
        for item in done.get("units", []):
            node_at(document, item["path"])["tr"] = item["tr"]
        for item in done.get("latex", []):
            node_at(document, item["path"])["latex"] = item["latex"]
        write_json(self._project.work_output(page), document)
        return self.finalize(page)


def node_at(document, path):
    """'blocks[3].sentences[1]' gibi bir yolun gösterdiği birim."""
    node = document
    for key, index in _PATH_STEP.findall(path):
        node = node[key] if key else node[int(index)]
    return node


def _summary(document, pending):
    return {"units": len(PageDocument(document).text_units()), "pending": len(pending["units"]),
            "latex": len(pending["latex"]), "complete": not pending["units"] and not pending["latex"]}


def _apply_done(finisher, pages):
    for page in pages:
        result = finisher.apply(int(page))
        print(f"✓ sayfa {page} uygulandı ve sonlandırıldı (boş tr: {result['untranslated']})")


def _report_waiting(results):
    """--no-finalize: eksiksiz sayfa da sonlandırılmadan bekler; her sayfanın durumu basılır."""
    for result in results:
        _print_result(result, _waiting(result))


def _finalize_complete(finisher, results):
    """Eksiksiz taşınan sayfa hemen sonlandırılır; her sayfanın durumu basılır."""
    for result in results:
        if result["complete"]:
            finisher.finalize(result["page"])
        _print_result(result, FINALIZED if result["complete"] else _waiting(result))


def _migrated(project, args):
    """Taşıma sonuçları; sayfalar sırayla, sonuç istendikçe taşınır ki önceki sayfa sonlandırılıp
    basıldıktan sonra sıradaki taşınsın."""
    progress = project.load_progress()
    migrator = Migrator.for_progress(project, progress)
    pages = progress.translated_pages() if args == ["all"] else [int(a) for a in args]
    return (migrator.run(page) for page in pages)


def _waiting(result):
    return f"bekliyor (pending {result['pending']}, latex {result['latex']})"


def _print_result(result, status):
    print(f"sayfa {result['page']}: {result['units']} birim, {status}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    project = Project.discover()
    if args[:1] == ["apply"]:
        _apply_done(MigrationFinisher.for_project(project), args[1:])
    elif "--no-finalize" in sys.argv:
        _report_waiting(_migrated(project, args))
    else:
        _finalize_complete(MigrationFinisher.for_project(project), _migrated(project, args))


if __name__ == "__main__":
    main()
