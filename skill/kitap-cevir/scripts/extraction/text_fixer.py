"""OpenDataLoader metnini PyMuPDF bulgularıyla onarır: ligatür, tire, satır içi kod."""
import re

from extraction.text_utils import clean_ligatures, normalize_spaces


class TextFixer:
    """ODL metnini PyMuPDF bulgularıyla onarır: ligatür, tire, satır içi kod."""

    def __init__(self, layout):
        self.hyphen_fixes = layout["hyphen_fixes"]
        self.script_fixes = layout.get("script_fixes", {})
        self.inline_tokens = sorted(layout["inline_code"], key=len, reverse=True)

    def plain(self, text):
        text = normalize_spaces(clean_ligatures(text or ""))
        for wrong, right in self.hyphen_fixes.items():
            text = text.replace(wrong, right)
        return _fix_words(text, self.script_fixes)

    def rich(self, text):
        for token in self.inline_tokens:
            text = _mark_outside_code(text, token)
        return text


def _fix_words(text, fixes):
    """Sözcük düzeltmesi yalnız tam sözcükte uygulanır: 'ma' -> 'mᵃ' düzeltmesi
    'format' kelimesinin içini bozmamalı."""
    for wrong, right in fixes.items():
        text = re.sub(r"(?<!\w)" + re.escape(wrong) + r"(?!\w)", lambda _, r=right: r, text)
    return text


def _mark_outside_code(text, token):
    """Token'ı yalnız ters tırnak dışındaki bölümlerde işaretler; daha uzun
    bir token'ın içine ikinci kez işaret koymaz ('`3.14 × `10`^23`')."""
    pattern = re.compile(r"(?<![\w`])" + re.escape(token) + r"(?![\w`])")
    replacement = "`" + token.replace("\\", "\\\\") + "`"
    segments = re.split(r"(`[^`]*`)", text)
    return "".join(seg if seg.startswith("`") else pattern.sub(replacement, seg) for seg in segments)
