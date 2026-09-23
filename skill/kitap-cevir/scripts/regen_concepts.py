"""Çevrilmiş sayfaların kavram kartlarını yeniden ürettirir; sayfa metnine dokunmaz.

Kullanım (proje dizininde):
  python3 regen_concepts.py prepare 5 13 40-60  -> _work/cards/in/page-N.json (kart agent'ı girdisi)
  python3 regen_concepts.py prepare all         -> data/pages altındaki tüm sayfalar
  python3 regen_concepts.py apply 5 13 | all    -> _work/cards/out/page-N.json içindeki kartları
      denetler ve data/pages/page-N.js'e yazar; sorunlu sayfa yazılmaz, sorunları basılır.

Agent çıktısı: {"concepts": [...]} — sözleşme: references/FORMAT.md → Kavram kartları.
"""
import glob
import json
import os
import re
import sys

from concept_check import card_problems
from finalize_page import read_page_js, write_page_js
from project import Project, concepts_settings

_PAGE_FILE = re.compile(r"page-(\d+)\.js$")
_RANGE = re.compile(r"^(\d+)-(\d+)$")
_TEXT_TYPES = ("heading", "caption", "footnote", "chapter")


def translated_pages(project):
    matches = (_PAGE_FILE.search(path) for path in glob.glob(os.path.join(project.pages_dir, "page-*.js")))
    return sorted(int(match.group(1)) for match in matches if match)


def _expand(spec):
    match = _RANGE.match(spec)
    if match:
        return range(int(match.group(1)), int(match.group(2)) + 1)
    return [int(spec)]


def select_pages(project, specs):
    available = translated_pages(project)
    if specs == ["all"]:
        return available
    wanted = {page for spec in specs for page in _expand(spec)}
    missing = sorted(wanted - set(available))
    if missing:
        print(f"  ! çevrilmemiş sayfalar atlandı: {', '.join(map(str, missing))}")
    return [page for page in available if page in wanted]


def _joined(kind, units):
    return {"type": kind, "en": " ".join(unit.get("en", "") for unit in units),
            "tr": " ".join(unit.get("tr", "") for unit in units)}


def _block_unit(block):
    """Bloğu kart agent'ının okuyacağı tek bir {type, en, tr} birimine indirger."""
    kind = block["type"]
    if kind == "para":
        return _joined(kind, block["sentences"])
    if kind == "list":
        return _joined(kind, block["items"])
    if kind == "table":
        return _joined(kind, [cell for row in block["rows"] for cell in row])
    if kind == "code":
        return {"type": kind, "code": block["code"]}
    if kind in _TEXT_TYPES:
        return {"type": kind, "en": block.get("en", ""), "tr": block.get("tr", "")}
    return None


def card_input(page_document, spec):
    content = [unit for unit in map(_block_unit, page_document["blocks"]) if unit]
    return {"id": page_document["id"], "page": page_document["page"],
            "chapter": page_document.get("chapter", {}), "section": page_document.get("section", {}),
            "title": page_document.get("title", {}), "content": content,
            "concepts_spec": spec, "concepts": []}


def cards_path(project, stage, page):
    return os.path.join(project.work_cards, stage, f"page-{page}.json")


def prepare(project, pages):
    spec = concepts_settings(project.load_progress())
    for page in pages:
        path = cards_path(project, "in", page)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(card_input(read_page_js(project.page_js(page)), spec), handle,
                      ensure_ascii=False, indent=2)
    return [project.relative(cards_path(project, "in", page)) for page in pages]


def apply_cards(project, page, spec):
    """Kartları denetler, geçerliyse sayfaya yazar; sorun listesini döndürür."""
    with open(cards_path(project, "out", page), encoding="utf-8") as handle:
        cards = json.load(handle).get("concepts", [])
    problems = card_problems(cards, spec)
    if not problems:
        document = read_page_js(project.page_js(page))
        write_page_js(project, {**document, "concepts": cards})
    return problems


def apply(project, pages):
    spec = concepts_settings(project.load_progress())
    report = {}
    for page in pages:
        try:
            report[page] = apply_cards(project, page, spec)
        except FileNotFoundError:
            report[page] = [f"çıktı yok: {project.relative(cards_path(project, 'out', page))}"]
    return report


def _run_prepare(project, pages):
    paths = prepare(project, pages)
    print(f"Hazırlanan kart girdisi: {len(paths)}")
    for path in paths:
        print(f"  {path}")
    print("\nSonraki adım: her girdi için bir kart agent'ı (SKILL.md → C), "
          "çıktı _work/cards/out/page-N.json, sonra: regen_concepts.py apply ...")


def _run_apply(project, pages):
    report = apply(project, pages)
    for page, problems in report.items():
        print(f"  {'!' if problems else '✓'} Sayfa {page}")
        for problem in problems:
            print(f"      {problem}")
    written = sum(1 for problems in report.values() if not problems)
    print(f"\n{written}/{len(report)} sayfanın kartları yazıldı")


ACTIONS = {"prepare": _run_prepare, "apply": _run_apply}


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ACTIONS:
        print(__doc__)
        sys.exit(1)
    project = Project()
    ACTIONS[sys.argv[1]](project, select_pages(project, sys.argv[2:]))


if __name__ == "__main__":
    main()
