"""Çevrilmiş sayfa belgesi (data/pages/page-N.js → window.PAGE({...})): okunması,
yazılması ve çevrilecek metin birimleri. Şema: references/FORMAT.md.
"""
import json
import os
from collections import Counter

from page_blocks import Block

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

    def blocks(self):
        return [Block.of(data) for data in self.data["blocks"]]

    def text_units(self):
        return [unit for block in self.blocks() for unit in block.units()]

    def missing_translations(self):
        return sum(1 for unit in self.text_units() if unit.get("en") and not unit.get("tr"))

    def is_blank(self):
        """Yalnız görsel içeren sayfa (bölüm sonu boşluğu) çevrilecek bir şey taşımaz."""
        return all(block.kind == "image" for block in self.blocks())

    def display_math(self):
        return [block for block in self.data["blocks"] if block["type"] == "math"]

    def inline_math(self):
        return self.data.get("math", [])

    def equation_count(self):
        return len(self.display_math()) + len(self.inline_math())

    def media_sources(self):
        """Sayfanın görsel klasörüne kopyalanacak PNG adları."""
        sources = [src for block in self.blocks() for src in block.media_sources()]
        return sources + [item["src"] for item in self.inline_math()]

    def block_summary(self):
        counts = Counter(block.kind for block in self.blocks())
        return ", ".join(f"{kind}:{count}" for kind, count in counts.items())
