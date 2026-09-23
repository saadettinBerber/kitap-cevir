"""Çevrilmiş sayfaları yeni çıkarım yapısına taşır (yeniden çeviri yok).

  python3 migrate_page.py 5 13 121        -> sayfaları yeniden çıkarır, eski
      çevirileri yeni yapıya aktarır, _work/out/page-N.json yazar; eşleşmeyen
      birimler _work/migrate/pending-N.json'a düşer. Eksiksiz sayfalar hemen
      sonlandırılır (--no-finalize ile ertelenir).
  python3 migrate_page.py all              -> data/pages altındaki tüm sayfalar
  python3 migrate_page.py apply 13 31      -> _work/migrate/done-N.json içindeki
      çevirileri ({path, tr} ve {src, latex}) uygulayıp sonlandırır.
"""
import json
import os
import re
import sys

from extraction.text_layer.layout_scan import scan_page
from finalize_page import PageFinalizer
from migrate_match import TranslationFiller, Translations
from page_document import PageDocument
from prepare_page import PagePreparer
from project import Project, extraction_settings

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
        blocks = [{"path": f"blocks[{i}]", "src": b["src"]} for i, b in enumerate(self.document["blocks"])
                  if b["type"] == "math" and not b["latex"]]
        return blocks + [{"path": f"math[{i}]", "src": m["src"]}
                         for i, m in enumerate(PageDocument(self.document).inline_math()) if not m["latex"]]


class Migrator:
    """Projenin çevrilmiş sayfalarını taşır; bekleyenleri _work/migrate'e yazar."""

    def __init__(self):
        self.project = Project()
        self.preparer = PagePreparer(self.project)
        self.finalizer = PageFinalizer(self.project)
        self.migrate_dir = os.path.join(self.project.root, "_work", "migrate")
        os.makedirs(self.migrate_dir, exist_ok=True)

    def run(self, page, finalize_complete):
        old = PageDocument.read(self.project.page_js(page)).data
        document = self.preparer.build_input(page)
        pending, latex_items = PageMigration(document, old).run(self._fixes(document["pdf_page"]))
        os.makedirs(self.project.work_out, exist_ok=True)
        self._dump(self._out_path(page), document)
        self._write_pending(page, pending, latex_items)
        complete = not pending and not latex_items
        if complete and finalize_complete:
            self.finalizer.finalize(self._out_path(page))
        return {"page": page, "units": len(PageDocument(document).text_units()), "pending": len(pending),
                "latex": len(latex_items), "finalized": complete and finalize_complete}

    def apply(self, page):
        """done-N.json'daki çevirileri ({path, tr} ve {path, latex}) yazar ve sonlandırır."""
        done = self._load(os.path.join(self.migrate_dir, f"done-{page}.json"))
        document = self._load(self._out_path(page))
        for item in done.get("units", []):
            self._resolve(document, item["path"])["tr"] = item["tr"]
        for item in done.get("latex", []):
            self._resolve(document, item["path"])["latex"] = item["latex"]
        self._dump(self._out_path(page), document)
        return self.finalizer.finalize(self._out_path(page))

    def _fixes(self, pdf_page):
        settings = extraction_settings(self.preparer.progress)
        return scan_page(self.preparer.pdf, pdf_page, settings)["hyphen_fixes"]

    def _out_path(self, page):
        return os.path.join(self.project.work_out, f"page-{page}.json")

    def _write_pending(self, page, pending, latex_items):
        path = os.path.join(self.migrate_dir, f"pending-{page}.json")
        if pending or latex_items:
            self._dump(path, {"page": page, "units": pending, "latex": latex_items})
        elif os.path.exists(path):
            os.remove(path)

    @staticmethod
    def _resolve(document, path):
        """'blocks[3].sentences[1]' gibi bir yolun gösterdiği birim."""
        node = document
        for key, index in _PATH_STEP.findall(path):
            node = node[key] if key else node[int(index)]
        return node

    @staticmethod
    def _load(path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _dump(path, payload):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    finalize_complete = "--no-finalize" not in sys.argv
    migrator = Migrator()
    if args and args[0] == "apply":
        for page in args[1:]:
            result = migrator.apply(int(page))
            print(f"✓ sayfa {page} uygulandı ve sonlandırıldı (boş tr: {result['untranslated']})")
        return
    pages = migrator.project.translated_pages() if args == ["all"] else [int(a) for a in args]
    for page in pages:
        r = migrator.run(page, finalize_complete)
        state = "sonlandırıldı" if r["finalized"] else f"bekliyor (pending {r['pending']}, latex {r['latex']})"
        print(f"sayfa {r['page']}: {r['units']} birim, {state}")


if __name__ == "__main__":
    main()
