"""Metin temizleme ve cümle ayırma yardımcıları (PDF çıkarımı için)."""
import re

LIGATURES = {"ﬁ": "fi", "ﬀ": "ff", "ﬄ": "ffl", "ﬃ": "ffi", "ﬂ": "fl"}

ABBREVIATIONS = {
    "i.e.": "i<DOT>e<DOT>", "e.g.": "e<DOT>g<DOT>", "etc.": "etc<DOT>",
    "vs.": "vs<DOT>", "Dr.": "Dr<DOT>", "Mr.": "Mr<DOT>", "Ms.": "Ms<DOT>",
    "U.S.": "U<DOT>S<DOT>", "et al.": "et al<DOT>", "Fig.": "Fig<DOT>",
    "No.": "No<DOT>", "cf.": "cf<DOT>", "2d.": "2d<DOT>", "ed.": "ed<DOT>",
}

# Baş harf kısaltmaları ("Robert C. Martin", "O.-J. Dahl") cümle sonu sayılmaz.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])(?<![A-Z]\.)\s+(?=[A-Z“\"‘(\[])")
_NUMERIC_ONLY = re.compile(r"^[\d.,%\s]+$")


def clean_ligatures(text):
    for ligature, plain in LIGATURES.items():
        text = text.replace(ligature, plain)
    return text


def normalize_spaces(text):
    return re.sub(r"\s+", " ", text or "").strip()


def is_numeric_only(text):
    return bool(_NUMERIC_ONLY.match(text))


def split_sentences(paragraph):
    protected = paragraph
    for abbreviation, placeholder in ABBREVIATIONS.items():
        protected = protected.replace(abbreviation, placeholder)
    parts = _SENTENCE_BOUNDARY.split(protected)
    return [part.replace("<DOT>", ".").strip() for part in parts if part.strip()]


def strip_list_marker(text):
    return re.sub(r"^\s*(?:[•\-–*]|\d+[.)])\s+", "", text)
