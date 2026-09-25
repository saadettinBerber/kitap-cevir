"""Bölüm akışının parçaları. Kindle'da metin Türkçe akar; İngilizce aslı parçanın
sonundaki EN bağlantısına dokununca açılır pencerede görünür (EPUB 3 noteref → footnote).

Parçalar yalnız sorgu taşır: `english()` açılır notlarını, `render(first_note)` notları
first_note'tan numaralanmış XHTML'i döner. Numarayı bölüm dağıtır.
"""
import re

from epub.xhtml import visible_text

CONTINUATION_MARK = "…"   # çevirmen, önceki sayfada zaten çevrilmiş devamı böyle bırakır
SENTENCE_ENDINGS = tuple('.!?:…"”’)]')
_FOOTNOTE_MARK = re.compile(r"<sup>.*?</sup>")

NOTE_REF = '<a epub:type="noteref" id="ref-{n}" href="#note-{n}" class="en-ref">EN</a>'
NOTE = ('<aside epub:type="footnote" id="note-{n}" lang="en" xml:lang="en">'
        '<p><a href="#ref-{n}" class="back">↑</a> {en}</p></aside>')


def notes_section(english_texts):
    """Bölüm dosyasının sonundaki açılır notlar; Kindle onları akışta değil pencerede gösterir."""
    if not english_texts:
        return ""
    asides = "\n".join(NOTE.format(n=number, en=en) for number, en in enumerate(english_texts, 1))
    return f'<section class="notes">\n{asides}\n</section>'


class Fragment:
    """Akışa hazır işaretleme; açılır notu yoktur, sayfa sınırında bir öncekiyle birleşmez."""

    def __init__(self, html=""):
        self.html = html

    def english(self):
        return []

    def render(self, first_note):
        return self.html

    def continues_into(self, other):
        return False

    def toc_entries(self):
        return []


class Heading(Fragment):
    """Başlık; ilk düzey olanı Kindle içindekilerinde bölümün altında görünür."""

    def __init__(self, level, tr_html, anchor):
        super().__init__(f'<h{level + 1} id="{anchor}">{tr_html}</h{level + 1}>')
        self.level, self.tr_html, self.anchor = level, tr_html, anchor

    def toc_entries(self):
        return [(visible_text(self.tr_html), self.anchor)] if self.level == 1 else []


class Passage(Fragment):
    """İki dilli metin birimi: altyazı, dipnot ya da liste maddesi."""

    def __init__(self, css_class, tr_html, en_html):
        super().__init__()
        self.css_class, self.tr_html, self.en_html = css_class, tr_html, en_html

    def english(self):
        """Çevrilmemiş (İngilizcesine düşmüş) birimin açılır notu olmaz."""
        return [self.en_html] if self.en_html and self.en_html != self.tr_html else []

    def render(self, first_note):
        return f'<p class="{self.css_class}">{self.inline(first_note)}</p>'

    def inline(self, first_note):
        if not self.english():
            return self.tr_html
        return f"{self.tr_html} {NOTE_REF.format(n=first_note)}"


class ParaPassage(Passage):
    """Gövde paragrafı; sayfa sonunda yarım kalan cümle sonraki sayfada sürer."""

    def is_open(self):
        text = visible_text(_FOOTNOTE_MARK.sub("", self.en_html)).rstrip()
        return bool(text) and not text.endswith(SENTENCE_ENDINGS)

    def continues_into(self, other):
        return self.is_open() and isinstance(other, ParaPassage) and other.css_class == self.css_class

    def join(self, other, page_mark):
        """Devam paragrafı bu paragrafa katılır; sayfa işareti birleşme noktasında durur."""
        tr = other.tr_html.removeprefix(CONTINUATION_MARK).lstrip()
        return ParaPassage(self.css_class, f"{self.tr_html} {page_mark}{tr}", f"{self.en_html} {other.en_html}")


class PassageList(Fragment):
    """Madde listesi; her madde kendi açılır notunu taşır."""

    def __init__(self, ordered, passages):
        super().__init__()
        self.tag = "ol" if ordered else "ul"
        self.passages = passages

    def english(self):
        return [en for passage in self.passages for en in passage.english()]

    def render(self, first_note):
        items = "".join(f"<li>{passage.inline(note)}</li>"
                        for passage, note in zip(self.passages, self._note_numbers(first_note)))
        return f'<{self.tag} class="list">{items}</{self.tag}>'

    def _note_numbers(self, first_note):
        """Her maddenin ilk not numarası; notu olmayan madde numara tüketmez."""
        counts = [len(passage.english()) for passage in self.passages]
        return [first_note + sum(counts[:index]) for index in range(len(counts))]
