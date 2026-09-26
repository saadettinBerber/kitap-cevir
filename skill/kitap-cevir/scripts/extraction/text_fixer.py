"""OpenDataLoader metnini PyMuPDF bulgularıyla onarır: ligatür, tire, satır içi kod."""
import re

from extraction.text_utils import clean_ligatures, normalize_spaces


class TextFixer:
    """ODL metnini PyMuPDF bulgularıyla onarır: ligatür, tire, simgeli sözcük; zengin
    biçimde satır içi kodu da işaretler."""

    def __init__(self, layout):
        self._hyphen_fixes = layout["hyphen_fixes"]
        self._script_fixes = layout.get("script_fixes", {})
        self._inline_tokens = sorted(layout["inline_code"], key=len, reverse=True)

    def plain(self, text):
        text = normalize_spaces(clean_ligatures(text or ""))
        for wrong, right in self._hyphen_fixes.items():
            text = text.replace(wrong, right)
        return self._fix_words(text)

    def rich(self, text):
        """Onarılmış metin; satır içi kod parçaları ters tırnak içinde."""
        marked = self.plain(text)
        for token in self._inline_tokens:
            marked = self._mark_outside_code(marked, token)
        return marked

    def _fix_words(self, text):
        """Sözcük düzeltmesi yalnız tam sözcükte uygulanır: 'ma' -> 'mᵃ' düzeltmesi
        'format' kelimesinin içini bozmamalı."""
        for wrong, right in self._script_fixes.items():
            text = re.sub(r"(?<!\w)" + re.escape(wrong) + r"(?!\w)", lambda _, r=right: r, text)
        return text

    @staticmethod
    def _mark_outside_code(text, token):
        """Token'ı yalnız ters tırnak dışındaki bölümlerde işaretler; daha uzun
        bir token'ın içine ikinci kez işaret koymaz ('`3.14 × `10`^23`')."""
        pattern = re.compile(r"(?<![\w`])" + re.escape(token) + r"(?![\w`])")
        replacement = "`" + token.replace("\\", "\\\\") + "`"
        segments = re.split(r"(`[^`]*`)", text)
        return "".join(seg if seg.startswith("`") else pattern.sub(replacement, seg) for seg in segments)
