"""Kavram kartlarını (concepts) kitabın kart ayarlarına göre denetler.

Sorunlar metin listesi olarak döner; boş liste = kartlar geçerli. Kart türleri
ve alanları: references/FORMAT.md → Kavram kartları. finalize_page.py ve
regen_concepts.py kullanır.
"""
MIN_CARDS = 2
MAX_CARDS = 4
MIN_OPTIONS = 2
MAX_OPTIONS = 3
SIDES = ("bad", "good")
_LANG_ALIASES = {"js": "javascript", "py": "python", "ts": "typescript"}


def card_kind(card):
    """Kartın türü; `kind` alanı olmayan eski kartlarda içerikten çıkarılır."""
    if card.get("kind"):
        return card["kind"]
    if "body_html" in card:
        return "legacy"
    if "options" in card:
        return "tradeoff"
    sample = card.get("bad") or {}
    if sample.get("code"):
        return "code"
    return "contrast" if sample.get("text") else "explain"


def _missing_pair(unit, label):
    if not isinstance(unit, dict):
        return [f"{label} yok"]
    return [f"{label}.{lang} boş" for lang in ("en", "tr") if not str(unit.get(lang, "")).strip()]


def _normal_lang(lang):
    key = str(lang or "").lower()
    return _LANG_ALIASES.get(key, key)


def _duplicate_ids(cards):
    seen, duplicates = set(), []
    for card in cards:
        if card.get("id") in seen:
            duplicates.append(f"{card['id']}: id tekrar ediyor")
        seen.add(card.get("id"))
    return duplicates


class CardChecker:
    """Bir sayfanın kartlarını kitabın kart ayarlarına göre denetler;
    spec = project.concepts_settings(progress)."""

    def __init__(self, spec):
        self.spec = spec
        self.code_langs = {_normal_lang(lang) for lang in spec["code_langs"]}
        self.kind_checks = {"explain": self._explain_problems, "contrast": self._contrast_problems,
                            "tradeoff": self._tradeoff_problems, "code": self._code_problems}

    def problems(self, cards):
        problems = []
        if not MIN_CARDS <= len(cards) <= MAX_CARDS:
            problems.append(f"kart sayısı {len(cards)} ({MIN_CARDS}-{MAX_CARDS} olmalı)")
        for index, card in enumerate(cards, 1):
            label = card.get("id") or f"#{index}"
            problems += [f"{label}: {problem}" for problem in self._card_problems(card)]
        return problems + _duplicate_ids(cards)

    def _card_problems(self, card):
        kind = card_kind(card)
        if kind not in self.spec["kinds"]:
            return [f"tür {kind!r} bu kitapta izinli değil ({', '.join(self.spec['kinds'])})"]
        problems = [] if card.get("id") else ["id yok"]
        for field in ("title", "summary", "tip"):
            problems += _missing_pair(card.get(field), field)
        return problems + self.kind_checks[kind](card)

    def _code_problems(self, card):
        problems = []
        for side in SIDES:
            sample = card.get(side) or {}
            problems += self._code_side(sample, side) + _missing_pair(sample.get("why"), f"{side}.why")
        return problems

    def _code_side(self, sample, side):
        if not str(sample.get("code", "")).strip():
            return [f"{side}.code boş"]
        if _normal_lang(sample.get("lang")) not in self.code_langs:
            return [f"{side}.lang {sample.get('lang')!r} izinli değil ({', '.join(self.spec['code_langs'])})"]
        return []

    @staticmethod
    def _contrast_problems(card):
        problems = []
        for side in SIDES:
            sample = card.get(side) or {}
            body = [] if sample.get("code") else _missing_pair(sample.get("text"), f"{side}.text")
            problems += body + _missing_pair(sample.get("why"), f"{side}.why")
        return problems

    @staticmethod
    def _tradeoff_problems(card):
        options = card.get("options") or []
        problems = []
        if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            problems.append(f"options sayısı {len(options)} ({MIN_OPTIONS}-{MAX_OPTIONS} olmalı)")
        for index, option in enumerate(options, 1):
            for field in ("name", "gains", "costs"):
                problems += _missing_pair(option.get(field), f"options[{index}].{field}")
        return problems

    @staticmethod
    def _explain_problems(card):
        return [f"explain kartında `{field}` olmamalı" for field in SIDES + ("options",) if card.get(field)]
