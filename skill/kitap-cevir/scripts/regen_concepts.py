"""Çevrilmiş sayfaların kavram kartlarını yeniden ürettirir; sayfa metnine dokunmaz.

Kullanım (proje dizininde):
  python3 regen_concepts.py prepare 5 13 40-60  -> _work/cards/in/page-N.json (kart agent'ı girdisi)
  python3 regen_concepts.py prepare all         -> data/pages altındaki tüm sayfalar
  python3 regen_concepts.py apply 5 13 | all    -> _work/cards/out/page-N.json içindeki kartları
      denetler ve data/pages/page-N.js'e yazar; sorunlu sayfa yazılmaz, sorunları basılır.

Agent çıktısı: {"concepts": [...]} — sözleşme: references/FORMAT.md → Kavram kartları.
"""
import re
import sys

from concept_check import CardChecker
from json_file import read_json, write_json
from page_document import PageDocument
from project import Project

_RANGE = re.compile(r"^(\d+)-(\d+)$")


def select_pages(specs, available):
    """'all', tek numaralar ve '5-40' aralıkları; (seçilen, atlanan çevrilmemiş) sayfalar."""
    if specs == ["all"]:
        return available, []
    wanted = {page for spec in specs for page in _expand(spec)}
    return [page for page in available if page in wanted], sorted(wanted - set(available))


def _expand(spec):
    match = _RANGE.match(spec)
    return range(int(match.group(1)), int(match.group(2)) + 1) if match else [int(spec)]


class CardInputs:
    """Çevrilmiş sayfalardan kart agent'ının girdisini (_work/cards/in) hazırlar."""

    def __init__(self, project, spec):
        """spec = BookSettings.concepts(); agent'a gider, kart türlerini buna göre seçer."""
        self.project = project
        self.spec = spec

    @classmethod
    def for_project(cls, project):
        return cls(project, project.load_settings().concepts())

    def prepare(self, pages):
        for page in pages:
            path = self.project.work_cards_file("in", page)
            write_json(path, self.card_input(PageDocument.read(self.project.page_js(page)).data))
        return [self.project.relative_to_root(self.project.work_cards_file("in", page)) for page in pages]

    def card_input(self, page_data):
        content = [unit for unit in (block.card_unit() for block in PageDocument(page_data).blocks()) if unit]
        return {"id": page_data["id"], "page": page_data["page"],
                "chapter": page_data.get("chapter", {}), "section": page_data.get("section", {}),
                "title": page_data.get("title", {}), "content": content,
                "concepts_spec": self.spec, "concepts": []}


class CardOutputs:
    """Kart agent'ının çıktısını (_work/cards/out) denetler; geçerli kartları sayfaya yazar."""

    def __init__(self, project, checker):
        self.project = project
        self.checker = checker

    @classmethod
    def for_project(cls, project):
        return cls(project, CardChecker(project.load_settings().concepts()))

    def apply(self, pages):
        """{sayfa: sorunlar}; sorunsuz sayfaların kartları yazılmıştır."""
        report = {}
        for page in pages:
            try:
                report[page] = self._apply_page(page)
            except FileNotFoundError:
                report[page] = [f"çıktı yok: {self.project.relative_to_root(self.project.work_cards_file('out', page))}"]
        return report

    def _apply_page(self, page):
        cards = read_json(self.project.work_cards_file("out", page)).get("concepts", [])
        problems = self.checker.problems(cards)
        if not problems:
            document = PageDocument.read(self.project.page_js(page))
            PageDocument({**document.data, "concepts": cards}).write(self.project.page_js(document.data["page"]))
        return problems


def _run_prepare(project, pages):
    paths = CardInputs.for_project(project).prepare(pages)
    print(f"Hazırlanan kart girdisi: {len(paths)}")
    for path in paths:
        print(f"  {path}")
    print("\nSonraki adım: her girdi için bir kart agent'ı (SKILL.md → C), "
          "çıktı _work/cards/out/page-N.json, sonra: regen_concepts.py apply ...")


def _run_apply(project, pages):
    report = CardOutputs.for_project(project).apply(pages)
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
    project = Project.discover()
    pages, skipped = select_pages(sys.argv[2:], project.translated_pages())
    if skipped:
        print(f"  ! çevrilmemiş sayfalar atlandı: {', '.join(map(str, skipped))}")
    ACTIONS[sys.argv[1]](project, pages)


if __name__ == "__main__":
    main()
