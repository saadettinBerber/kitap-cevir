"""OpenDataLoader metnini PyMuPDF bulgularıyla onarır: ligatür, tire, satır içi kod."""
import re

from text_utils import clean_ligatures, normalize_spaces


class TextFixer:
    """ODL metnini PyMuPDF bulgularıyla onarır: ligatür, tire, satır içi kod."""

    def __init__(self, layout):
        self.hyphen_fixes = layout["hyphen_fixes"]
        self.inline_tokens = sorted(layout["inline_code"], key=len, reverse=True)

    def plain(self, text):
        text = normalize_spaces(clean_ligatures(text or ""))
        for wrong, right in self.hyphen_fixes.items():
            text = text.replace(wrong, right)
        return text

    def rich(self, text):
        for token in self.inline_tokens:
            pattern = r"(?<![\w`])" + re.escape(token) + r"(?![\w`])"
            text = re.sub(pattern, "`" + token.replace("\\", "\\\\") + "`", text)
        return text
