"""Kavram kartlarını (concepts) kitabın kart ayarlarına göre denetler.

Sorunlar metin listesi olarak döner; boş liste = kartlar geçerli. Kart türleri ve alanları:
references/FORMAT.md → Kavram kartları. Kart bir veri yapısıdır: türü Card.of'ta bulunur, türe
özgü kurallar CardRules ziyaretçisindedir. Kart türleri sabit, kart üzerindeki işlemler (denetim,
çizim) çoğalıyor; bu yüzden ortak kurallar sözlük üzerinde çalışan fonksiyonlardır (Bl.6).
"""
from concept_cards import Card

SIDES = ("bad", "good")
COMMON_PAIRS = ("title", "summary", "tip")
OPTION_FIELDS = ("name", "gains", "costs")
_LANG_ALIASES = {"js": "javascript", "py": "python", "ts": "typescript"}


class CountLimit:
    """Bir listenin izinli uzunluğu; aralığın dışındaki liste tek bir sorun verir."""

    def __init__(self, noun, bounds):
        self._noun = noun
        self._low, self._high = bounds

    def problems(self, items):
        if self._low <= len(items) <= self._high:
            return []
        return [f"{self._noun} sayısı {len(items)} ({self._low}-{self._high} olmalı)"]


CARD_LIMIT = CountLimit("kart", (2, 4))
OPTION_LIMIT = CountLimit("options", (2, 3))


class CardChecker:
    """Bir sayfanın kartlarını kitabın kart ayarlarına göre denetler;
    spec = BookSettings.concepts()."""

    def __init__(self, spec):
        self._allowed_kinds = spec["kinds"]
        self._rules = CardRules(spec["code_langs"])

    def problems(self, cards):
        return CARD_LIMIT.problems(cards) + self._named_card_problems(cards) + _duplicate_ids(cards)

    def _named_card_problems(self, cards):
        """Her sorun kartın kimliğiyle başlar; kimliği olmayan kart sırasıyla anılır."""
        names = [card.get("id") or f"#{index}" for index, card in enumerate(cards, 1)]
        return [f"{name}: {problem}" for name, card in zip(names, cards) for problem in self._card_problems(card)]

    def _card_problems(self, card):
        typed = Card.of(card)
        if typed.kind() not in self._allowed_kinds:
            return [f"tür {typed.kind()!r} bu kitapta izinli değil ({', '.join(self._allowed_kinds)})"]
        return _common_problems(card) + typed.accept(self._rules)


def _duplicate_ids(cards):
    seen, duplicates = set(), []
    for card in cards:
        if card.get("id") in seen:
            duplicates.append(f"{card['id']}: id tekrar ediyor")
        seen.add(card.get("id"))
    return duplicates


def _common_problems(card):
    """Her türde zorunlu alanlar: id ve iki dilli title, summary, tip."""
    problems = [] if card.get("id") else ["id yok"]
    for field in COMMON_PAIRS:
        problems += _missing_pair(card.get(field), field)
    return problems


class CardRules:
    """Türe özgü kurallar (VISITOR, Bl.6): tür dallanması Card.of'ta kalır, yeni tür buraya bir
    visit_* metoduyla eklenir. bad/good taraflı türlerde yalnız gövdenin kuralı değişir."""

    def __init__(self, code_langs):
        self._langs = code_langs
        self._normal_langs = {_normal_lang(lang) for lang in code_langs}

    def visit_unknown(self, card):
        """İzinsiz tür CardChecker'da durur; buraya yalnız izinli türler gelir."""
        return []

    def visit_explain(self, card):
        """Yalnız ortak alanlar; örnek ya da seçenek taşımaz."""
        return [f"explain kartında `{field}` olmamalı" for field in SIDES + ("options",) if card.get(field)]

    def visit_tradeoff(self, card):
        """2-3 seçenek; her seçeneğin adı, kazancı ve bedeli vardır."""
        options = card.get("options") or []
        return OPTION_LIMIT.problems(options) + _problems_per_option(options)

    def visit_contrast(self, card):
        return self._sided(card, _text_body_problems)

    def visit_code(self, card):
        return self._sided(card, self._code_body_problems)

    @staticmethod
    def _sided(card, body_problems):
        """Her tarafın bir gövdesi ve iki dilli `why` açıklaması vardır."""
        return [problem for side, sample in _samples(card)
                for problem in body_problems(sample, side) + _missing_pair(sample.get("why"), f"{side}.why")]

    def _code_body_problems(self, sample, side):
        """Gövde, kitabın izin verdiği dilde koddur."""
        if not str(sample.get("code", "")).strip():
            return [f"{side}.code boş"]
        if _normal_lang(sample.get("lang")) not in self._normal_langs:
            return [f"{side}.lang {sample.get('lang')!r} izinli değil ({', '.join(self._langs)})"]
        return []


def _problems_per_option(options):
    return [problem for index, option in enumerate(options, 1) for problem in _missing_option_fields(option, index)]


def _missing_option_fields(option, index):
    return [problem for field in OPTION_FIELDS
            for problem in _missing_pair(option.get(field), f"options[{index}].{field}")]


def _samples(card):
    """(taraf, örnek) çiftleri; eksik taraf boş örnektir."""
    return [(side, card.get(side) or {}) for side in SIDES]


def _text_body_problems(sample, side):
    """Gövde iki dilli metindir; kod taşıyan taraf metinsiz olabilir."""
    if sample.get("code"):
        return []
    return _missing_pair(sample.get("text"), f"{side}.text")


def _missing_pair(unit, label):
    if not isinstance(unit, dict):
        return [f"{label} yok"]
    return [f"{label}.{lang} boş" for lang in ("en", "tr") if not str(unit.get(lang, "")).strip()]


def _normal_lang(lang):
    key = str(lang or "").lower()
    return _LANG_ALIASES.get(key, key)
