"""Çevrilmiş sayfaların kavram kartlarını yeniden ürettirir; sayfa metnine dokunmaz.

Kullanım (proje dizininde):
  python3 regen_concepts.py prepare 5 13 40-60  -> _work/cards/in/page-N.json (kart agent'ı girdisi)
  python3 regen_concepts.py prepare all         -> data/pages altındaki tüm sayfalar
  python3 regen_concepts.py apply 5 13 | all    -> _work/cards/out/page-N.json içindeki kartları
      denetler ve data/pages/page-N.js'e yazar; sorunlu sayfa yazılmaz, sorunları basılır.

Agent çıktısı: {"concepts": [...]} — sözleşme: references/FORMAT.md → Kavram kartları.
"""
import json
import os
import re
import sys

from concept_check import CardChecker
from page_document import PageDocument
from project import Project, concepts_settings

_RANGE = re.compile(r"^(\d+)-(\d+)$")


class CardRegenerator:
    """Bir projenin çevrilmiş sayfaları için kart agent'ı girdisini hazırlar ve
    agent çıktısını denetleyip sayfalara yazar."""

    def __init__(self, project, checker):
        self.project = project
        self.checker = checker

    @classmethod
    def for_project(cls, project):
        return cls(project, CardChecker(concepts_settings(project.load_progress())))

    def select_pages(self, specs):
        """'all', tek numaralar ve '5-40' aralıkları; çevrilmemiş sayfalar atlanır."""
        available = self.project.translated_pages()
        if specs == ["all"]:
            return available
        wanted = {page for spec in specs for page in self._expand(spec)}
        missing = sorted(wanted - set(available))
        if missing:
            print(f"  ! çevrilmemiş sayfalar atlandı: {', '.join(map(str, missing))}")
        return [page for page in available if page in wanted]

    @staticmethod
    def _expand(spec):
        match = _RANGE.match(spec)
        return range(int(match.group(1)), int(match.group(2)) + 1) if match else [int(spec)]

    def cards_path(self, stage, page):
        return os.path.join(self.project.work_cards, stage, f"page-{page}.json")

    def prepare(self, pages):
        for page in pages:
            path = self.cards_path("in", page)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(self.card_input(PageDocument.read(self.project.page_js(page)).data), handle,
                          ensure_ascii=False, indent=2)
        return [self.project.relative(self.cards_path("in", page)) for page in pages]

    def card_input(self, page_data):
        content = [unit for unit in (block.card_unit() for block in PageDocument(page_data).blocks()) if unit]
        return {"id": page_data["id"], "page": page_data["page"],
                "chapter": page_data.get("chapter", {}), "section": page_data.get("section", {}),
                "title": page_data.get("title", {}), "content": content,
                "concepts_spec": self.checker.spec, "concepts": []}

    def apply(self, pages):
        """{sayfa: sorunlar}; sorunsuz sayfaların kartları yazılmıştır."""
        report = {}
        for page in pages:
            try:
                report[page] = self._apply_page(page)
            except FileNotFoundError:
                report[page] = [f"çıktı yok: {self.project.relative(self.cards_path('out', page))}"]
        return report

    def _apply_page(self, page):
        with open(self.cards_path("out", page), encoding="utf-8") as handle:
            cards = json.load(handle).get("concepts", [])
        problems = self.checker.problems(cards)
        if not problems:
            document = PageDocument.read(self.project.page_js(page))
            PageDocument({**document.data, "concepts": cards}).write(self.project.pages_dir)
        return problems


def _run_prepare(regenerator, pages):
    paths = regenerator.prepare(pages)
    print(f"Hazırlanan kart girdisi: {len(paths)}")
    for path in paths:
        print(f"  {path}")
    print("\nSonraki adım: her girdi için bir kart agent'ı (SKILL.md → C), "
          "çıktı _work/cards/out/page-N.json, sonra: regen_concepts.py apply ...")


def _run_apply(regenerator, pages):
    report = regenerator.apply(pages)
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
    regenerator = CardRegenerator.for_project(Project())
    ACTIONS[sys.argv[1]](regenerator, regenerator.select_pages(sys.argv[2:]))


if __name__ == "__main__":
    main()
