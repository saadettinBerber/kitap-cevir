"""Çevrilmiş sayfa belgesi (data/pages/page-N.js → window.PAGE({...})): okunması,
yazılması ve çevrilecek metin birimleri. Şema: references/FORMAT.md.
"""
import json
import os

TEXT_BLOCK_TYPES = ("heading", "caption", "footnote", "chapter")
PRIVATE_FIELDS = ("context", "concepts_spec", "glossary_new")   # agent girdisinde var, okuyucuya gitmez


class PageDocument:
    """Bir sayfanın belgesi; `data` sözlüğü FORMAT.md şemasıdır."""

    def __init__(self, data):
        self.data = data

    @classmethod
    def read(cls, path):
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        return cls(json.loads(source[source.index("(") + 1:source.rindex(")")]))

    def write(self, pages_dir):
        os.makedirs(pages_dir, exist_ok=True)
        payload = {key: value for key, value in self.data.items() if key not in PRIVATE_FIELDS}
        path = os.path.join(pages_dir, f"{self.data['id']}.js")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("window.PAGE(" + json.dumps(payload, ensure_ascii=False) + ");\n")
        return path

    @staticmethod
    def block_units(block):
        """Bloğun çevrilecek {en, tr} birimleri: cümleler, maddeler, hücreler ya da bloğun kendisi."""
        if block["type"] == "para":
            return block["sentences"]
        if block["type"] == "list":
            return block["items"]
        if block["type"] == "table":
            return [cell for row in block["rows"] for cell in row]
        return [block] if block["type"] in TEXT_BLOCK_TYPES else []

    def text_units(self):
        return [unit for block in self.data["blocks"] for unit in self.block_units(block)]

    def missing_translations(self):
        return sum(1 for unit in self.text_units() if unit.get("en") and not unit.get("tr"))
