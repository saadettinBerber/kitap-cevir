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
TOC_LEVEL = 1

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
        self._html = html

    def english(self):
        return []

    def render(self, first_note):
        return self._html

    def continues_into(self, other):
        return False

    def toc_entries(self):
        return []


class Heading(Fragment):
    """Başlık; h1 bölüm başlığına ayrıldığı için bir düzey aşağıda çizilir. İlk düzey olanı Kindle
    içindekilerinde bölümün altında görünür."""

    def __init__(self, level, tr_html, anchor):
        tag = f"h{level + 1}"
        super().__init__(f'<{tag} id="{anchor}">{tr_html}</{tag}>')
        self._toc_entries = [(visible_text(tr_html), anchor)] if level == TOC_LEVEL else []

    def toc_entries(self):
        return self._toc_entries


class Passage:
    """İki dilli satır içi metin: Türkçesi akışta durur, İngilizcesi EN bağlantısıyla açılan nottur."""

    def __init__(self, tr_html, en_html):
        self._tr_html = tr_html
        self._en_html = en_html

    def english(self):
        """Çevrilmemiş (İngilizcesine düşmüş) metnin açılır notu olmaz."""
        return [self._en_html] if self._en_html and self._en_html != self._tr_html else []

    def inline(self, first_note):
        if not self.english():
            return self._tr_html
        return f"{self._tr_html} {NOTE_REF.format(n=first_note)}"

    def is_open(self):
        """İngilizcesi cümle sonu işaretiyle bitmeyen metin sayfa sonunda yarım kalmıştır."""
        text = visible_text(_FOOTNOTE_MARK.sub("", self._en_html)).rstrip()
        return bool(text) and not text.endswith(SENTENCE_ENDINGS)

    def join(self, continuation, page_mark):
        """Devam metni bu metne katılır; sayfa işareti birleşme noktasında durur."""
        tr = continuation._tr_html.removeprefix(CONTINUATION_MARK).lstrip()
        return Passage(f"{self._tr_html} {page_mark}{tr}", f"{self._en_html} {continuation._en_html}")


class Paragraph(Fragment):
    """Sınıfıyla çizilen paragraf: altyazı ya da dipnot."""

    def __init__(self, css_class, passage):
        super().__init__()
        self._css_class = css_class
        self._passage = passage

    def english(self):
        return self._passage.english()

    def render(self, first_note):
        return f'<p class="{self._css_class}">{self._passage.inline(first_note)}</p>'


class BodyParagraph(Paragraph):
    """Gövde paragrafı; sayfa sonunda yarım kalan cümle sonraki sayfada sürer."""

    def continues_into(self, other):
        return self._passage.is_open() and self._has_style_of(other)

    def _has_style_of(self, other):
        return isinstance(other, BodyParagraph) and other._css_class == self._css_class

    def join(self, other, page_mark):
        """Devam paragrafı bu paragrafa katılır."""
        return BodyParagraph(self._css_class, self._passage.join(other._passage, page_mark))


class PassageList(Fragment):
    """Madde listesi; her madde kendi açılır notunu taşır."""

    def __init__(self, tag, passages):
        super().__init__()
        self._tag = tag
        self._passages = passages

    def english(self):
        return [en for passage in self._passages for en in passage.english()]

    def render(self, first_note):
        items = "".join(f"<li>{passage.inline(note)}</li>"
                        for passage, note in zip(self._passages, self._note_numbers(first_note)))
        return f'<{self._tag} class="list">{items}</{self._tag}>'

    def _note_numbers(self, first_note):
        """Her maddenin ilk not numarası; notu olmayan madde numara tüketmez."""
        counts = [len(passage.english()) for passage in self._passages]
        return [first_note + sum(counts[:index]) for index in range(len(counts))]
