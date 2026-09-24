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


class ExplainRules:
    """explain kartı yalnız ortak alanları taşır; örnek ya da seçenek taşımaz."""

    def problems(self, card):
        return [f"explain kartında `{field}` olmamalı" for field in SIDES + ("options",) if card.get(field)]


class TradeoffRules:
    """tradeoff kartı 2-3 seçenek taşır; her seçeneğin adı, kazancı ve bedeli vardır."""

    def problems(self, card):
        options = card.get("options") or []
        problems = []
        if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            problems.append(f"options sayısı {len(options)} ({MIN_OPTIONS}-{MAX_OPTIONS} olmalı)")
        for index, option in enumerate(options, 1):
            for field in ("name", "gains", "costs"):
                problems += _missing_pair(option.get(field), f"options[{index}].{field}")
        return problems


class SidedRules:
    """bad/good taraflı kartlar (TEMPLATE METHOD): her tarafın bir gövdesi ve iki
    dilli `why` açıklaması vardır; gövdenin ne olduğunu alt sınıf söyler."""

    def problems(self, card):
        problems = []
        for side in SIDES:
            sample = card.get(side) or {}
            problems += self._body_problems(sample, side) + _missing_pair(sample.get("why"), f"{side}.why")
        return problems

    def _body_problems(self, sample, side):
        raise NotImplementedError


class ContrastRules(SidedRules):
    """contrast tarafının gövdesi iki dilli metindir; kod taşıyan taraf metinsiz olabilir."""

    def _body_problems(self, sample, side):
        if sample.get("code"):
            return []
        return _missing_pair(sample.get("text"), f"{side}.text")


class CodeRules(SidedRules):
    """code tarafının gövdesi kitabın izin verdiği dilde koddur."""

    def __init__(self, langs):
        self.langs = langs
        self.normal_langs = {_normal_lang(lang) for lang in langs}

    def _body_problems(self, sample, side):
        if not str(sample.get("code", "")).strip():
            return [f"{side}.code boş"]
        if _normal_lang(sample.get("lang")) not in self.normal_langs:
            return [f"{side}.lang {sample.get('lang')!r} izinli değil ({', '.join(self.langs)})"]
        return []


def kind_rules(code_langs):
    """Kart türünden kurallarına; yeni kart türü buraya bir kural sınıfıyla eklenir."""
    return {"explain": ExplainRules(), "contrast": ContrastRules(),
            "tradeoff": TradeoffRules(), "code": CodeRules(code_langs)}


class CardChecker:
    """Bir sayfanın kartlarını kitabın kart ayarlarına göre denetler;
    spec = BookSettings.concepts()."""

    def __init__(self, spec):
        rules = kind_rules(spec["code_langs"])
        self.allowed_rules = {kind: rules[kind] for kind in spec["kinds"]}

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
        if kind not in self.allowed_rules:
            return [f"tür {kind!r} bu kitapta izinli değil ({', '.join(self.allowed_rules)})"]
        problems = [] if card.get("id") else ["id yok"]
        for field in ("title", "summary", "tip"):
            problems += _missing_pair(card.get(field), field)
        return problems + self.allowed_rules[kind].problems(card)
