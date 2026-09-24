"""Bölüm açılışının blokları tek chapter bloğunda birleşir; blok kurulduktan
sonra sayfanın blok listesi üzerinde çalışır."""
import re

_CHAPTER_AUTHOR = re.compile(r"^(?:by|with) [A-Z]")


class ChapterOpener:
    """Bölüm açılışı düzen okuyucusunda ayrı öğeler olarak gelir: chapter_number + chapter +
    'by ...' paragrafı. Bunlar tek chapter bloğunda birleşir."""

    def __init__(self, blocks):
        self.blocks = blocks

    def merged(self):
        merged, pending_number = [], None
        for block in self.blocks:
            if block["type"] == "chapter_number":
                pending_number = block["num"]
            elif block["type"] == "chapter":
                block["num"] = pending_number
                merged.append(block)
            elif merged and merged[-1]["type"] == "chapter" and self._author_line(block):
                merged[-1]["author"] = self._author_line(block)
            else:
                merged.append(block)
        return merged

    @staticmethod
    def _author_line(block):
        if block.get("type") != "para" or len(block["sentences"]) != 1:
            return ""
        text = block["sentences"][0]["en"]
        return text if _CHAPTER_AUTHOR.match(text) else ""
