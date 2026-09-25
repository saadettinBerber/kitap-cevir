"""Kavram kartlarının türü (references/FORMAT.md → Kavram kartları).

Kart türüne göre dallanma yalnız `Card.of` fabrikasındadır. Kartlar JSON sözlüğünü sarar,
veri biçimi değişmez.
"""


class Card:
    """Türü bilinmeyen kart; türü, kartın kendi yazdığıdır."""
    KIND = None

    def __init__(self, data):
        self._data = data

    @staticmethod
    def of(data):
        return _CARD_CLASSES.get(data.get("kind") or _inferred_kind(data), Card)(data)

    def kind(self):
        return self.KIND or self._data.get("kind")


class ExplainCard(Card):
    KIND = "explain"


class ContrastCard(Card):
    KIND = "contrast"


class TradeoffCard(Card):
    KIND = "tradeoff"


class CodeCard(Card):
    KIND = "code"


def _inferred_kind(data):
    """`kind` alanı olmayan eski kartların türü içerikten çıkarılır."""
    if "options" in data:
        return TradeoffCard.KIND
    sample = data.get("bad") or {}
    if sample.get("code"):
        return CodeCard.KIND
    return ContrastCard.KIND if sample.get("text") else ExplainCard.KIND


_CARD_CLASSES = {card_class.KIND: card_class for card_class in (ExplainCard, ContrastCard, TradeoffCard, CodeCard)}
