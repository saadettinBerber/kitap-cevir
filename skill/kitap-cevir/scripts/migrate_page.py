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

from finalize_page import finalize, read_page_js
from extraction.text_layer.layout_scan import scan_page
from migrate_match import Translations, apply_fixes, fill_sentences, fill_unit, old_units
from prepare_page import PagePreparer
from project import Project, extraction_settings

_TEXT_TYPES = ("heading", "caption", "footnote", "chapter")
_COPY_FIELDS = ("title", "section", "concepts")


def _fill_block(block, translations, pending, path):
    if block["type"] == "para":
        block["sentences"] = fill_sentences(block["sentences"], translations, pending, path)
    elif block["type"] == "list":
        for i, item in enumerate(block["items"]):
            fill_unit(item, translations, pending, f"{path}.items[{i}]")
    elif block["type"] == "table":
        for r, row in enumerate(block["rows"]):
            for c, cell in enumerate(row):
                fill_unit(cell, translations, pending, f"{path}.rows[{r}][{c}]")
    elif block["type"] in _TEXT_TYPES:
        fill_unit(block, translations, pending, path)


def _carry_latex(document, old):
    """Eski sayfada aynı PNG için LaTeX yazılmışsa yeni yapıya taşınır."""
    known = {m["src"]: m.get("latex", "") for m in old.get("math", [])}
    known.update({b["src"]: b.get("latex", "") for b in old["blocks"] if b["type"] == "math"})
    for item in [b for b in document["blocks"] if b["type"] == "math"] + document.get("math", []):
        item["latex"] = item.get("latex") or known.get(item["src"], "")


def _math_items(document):
    items = [{"path": f"blocks[{i}]", "src": b["src"]}
             for i, b in enumerate(document["blocks"]) if b["type"] == "math" and not b["latex"]]
    items += [{"path": f"math[{i}]", "src": m["src"]}
              for i, m in enumerate(document.get("math", [])) if not m["latex"]]
    return items


def migrate(document, old, fixes):
    """Yeni girdiye eski çevirileri işler; (pending, latex_items) döndürür."""
    units = apply_fixes(old_units(old["blocks"]), fixes)
    translations, pending = Translations(units), []
    for index, block in enumerate(document["blocks"]):
        _fill_block(block, translations, pending, f"blocks[{index}]")
    for field in _COPY_FIELDS:
        document[field] = old.get(field, document.get(field))
    _carry_latex(document, old)
    if not document.get("chapter", {}).get("tr"):
        document["chapter"] = old.get("chapter", document["chapter"])
    document["glossary_new"] = []
    return pending, _math_items(document)


class Migrator:
    def __init__(self):
        self.project = Project()
        self.preparer = PagePreparer(self.project)
        self.migrate_dir = os.path.join(self.project.root, "_work", "migrate")
        os.makedirs(self.migrate_dir, exist_ok=True)

    def _fixes(self, pdf_page):
        settings = extraction_settings(self.preparer.progress)
        return scan_page(self.preparer.pdf, pdf_page, settings)["hyphen_fixes"]

    def _out_path(self, page):
        return os.path.join(self.project.work_out, f"page-{page}.json")

    def run(self, page, finalize_complete):
        old = read_page_js(self.project.page_js(page))
        document = self.preparer.build_input(page)
        pending, latex_items = migrate(document, old, self._fixes(document["pdf_page"]))
        os.makedirs(self.project.work_out, exist_ok=True)
        _dump(self._out_path(page), document)
        self._write_pending(page, pending, latex_items)
        complete = not pending and not latex_items
        if complete and finalize_complete:
            finalize(self.project, self._out_path(page))
        return {"page": page, "units": _unit_count(document), "pending": len(pending),
                "latex": len(latex_items), "finalized": complete and finalize_complete}

    def _write_pending(self, page, pending, latex_items):
        path = os.path.join(self.migrate_dir, f"pending-{page}.json")
        if pending or latex_items:
            _dump(path, {"page": page, "units": pending, "latex": latex_items})
        elif os.path.exists(path):
            os.remove(path)

    def apply(self, page):
        done = json.load(open(os.path.join(self.migrate_dir, f"done-{page}.json"), encoding="utf-8"))
        document = json.load(open(self._out_path(page), encoding="utf-8"))
        for item in done.get("units", []):
            _resolve(document, item["path"])["tr"] = item["tr"]
        for item in done.get("latex", []):
            _resolve(document, item["path"])["latex"] = item["latex"]
        _dump(self._out_path(page), document)
        return finalize(self.project, self._out_path(page))


def _resolve(document, path):
    node = document
    for key in re.findall(r"(\w+)|\[(\d+)\]", path):
        node = node[key[0]] if key[0] else node[int(key[1])]
    return node


def _unit_count(document):
    counter = []
    for block in document["blocks"]:
        _fill_block_count(block, counter)
    return len(counter)


def _fill_block_count(block, counter):
    if block["type"] == "para":
        counter += block["sentences"]
    elif block["type"] == "list":
        counter += block["items"]
    elif block["type"] == "table":
        counter += [c for row in block["rows"] for c in row]
    elif block["type"] in _TEXT_TYPES:
        counter.append(block)


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
