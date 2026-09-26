"""Bölüm açılışının blokları tek chapter bloğunda birleşir; blok kurulduktan
sonra sayfanın blok listesi üzerinde çalışır."""
import re

_CHAPTER_AUTHOR = re.compile(r"^(?:by|with) [A-Z]")


class ChapterOpener:
    """Bölüm açılışı düzen okuyucusunda ayrı öğeler olarak gelir: chapter_number + chapter +
    'by ...' paragrafı. Bunlar tek chapter bloğunda birleşir; gelen bloklar değişmez."""

    def __init__(self, blocks):
        self._blocks = blocks

    def merged(self):
        return self._with_authors(self._with_numbers())

    def _with_numbers(self):
        """chapter_number bloğu düşer; numarası sonraki bölüm başlıklarına geçer."""
        numbered, number = [], None
        for block in self._blocks:
            if block["type"] == "chapter_number":
                number = block["num"]
            else:
                numbered.append({**block, "num": number} if block["type"] == "chapter" else block)
        return numbered

    def _with_authors(self, blocks):
        """Bölüm başlığının hemen ardındaki yazar satırı başlığın `author` alanı olur."""
        merged = []
        for block in blocks:
            author = self._author_line(block) if merged and merged[-1]["type"] == "chapter" else ""
            if author:
                merged[-1] = {**merged[-1], "author": author}
            else:
                merged.append(block)
        return merged

    @staticmethod
    def _author_line(block):
        if block.get("type") != "para" or len(block["sentences"]) != 1:
            return ""
        text = block["sentences"][0]["en"]
        return text if _CHAPTER_AUTHOR.match(text) else ""
