"""Alt/üst simgeler: PyMuPDF simgeyi ('10' üstünde '23', cümlede 'mᵃ') ayrı satır
olarak verir, ODL ise düz karaktere indirger. Simge ev sahibi satıra x konumuna
göre bağlanır; kodda '^23' / '_K' olarak dizilir, gövde metninde Unicode
karşılığıyla sözcük düzeltmesine dönüşür.
"""
from dataclasses import replace
from itertools import islice
from typing import NamedTuple

from extraction.text_layer.text_line import Piece, TextLine, char_width, uses_script_layout

SCRIPT_SIZE_RATIO = 0.85          # ev sahibi puntosunun altındaki kaydırılmış parça = alt/üst simge
SCRIPT_SHIFT_RATIO = 0.12         # taban çizgisi kayması / punto: bunun üstü üst (^) ya da alt (_) simge
PROSE_SCRIPT_MIN_SIZE_RATIO = 0.7 # gövde metninde bundan küçük parça dipnot işaretidir, simge değil
PROSE_SCRIPT_MAX_GAP = 1.5        # simge, ev sahibi parçanın sağ kenarına bu kadar yakın başlar
SCRIPT_RUN_MAX_GAP = 2.0          # aynı taban çizgisinde bu kadar uzak parçalar ayrı simgelerdir
PROSE_SCRIPT_MAX_HOST_CHARS = 2   # gövde metninde simge sembole yapışır; uzun sözcüğünki dipnot göndermesidir

SUPERSCRIPTS = str.maketrans("0123456789abcdefghijklmnoprstuvwxyz+-=()",
                             "⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ⁺⁻⁼⁽⁾")
SUBSCRIPTS = str.maketrans("0123456789aehijklmnoprstuvx+-=()",
                           "₀₁₂₃₄₅₆₇₈₉ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ₊₋₌₍₎")


class ScriptMark:
    """Ev sahibi satıra bağlanmış bir simge; `marker` '^' (üst) ya da '_' (alt)."""

    def __init__(self, part, marker):
        self._left, self._right = part.box.x0, part.box.x1
        self._marker = marker
        self._body = part.raw_text.strip()

    def as_unicode(self):
        """Unicode karşılığı; karşılığı olmayan karakter varsa '^' / '_' gösterimi."""
        table = SUPERSCRIPTS if self._marker == "^" else SUBSCRIPTS
        if self._body and all(ord(char) in table for char in self._body):
            return self._body.translate(table)
        return self._notation()

    def piece(self):
        """Satır metnine x konumuna göre dizilen '^23' / '_K' parçası."""
        return Piece(self._left, self._right, self._notation(), is_script=True)

    def word_fix(self, line):
        """{düz: simgeli} sözcük düzeltmesi ('ma' -> 'mᵃ'); simgenin solunda sözcük yoksa boş."""
        word = _word_before(line, self._left)
        return {word + self._body: word + self.as_unicode()} if word and self._body else {}

    def _notation(self):
        return self._marker + self._body


def _word_before(line, left):
    """Satırda verilen konumun solunda kalan son sözcük; simge sembole bu kadar yakın başlar."""
    head = "".join(span.text for span in line.spans if span.box.x1 <= left + PROSE_SCRIPT_MAX_GAP).split()
    return head[-1] if head else ""


class _Placement(NamedTuple):
    """Bir satırın parça dizisinin yeri: `attachments` tek (ev sahibi satır, simge) çiftidir,
    parça dizisi kendi satırında kalıyorsa boştur."""
    source: TextLine
    spans: list
    attachments: tuple


def _kept(line, placements):
    """[simgeleri eklenmiş, simge olarak bağlanan parçaları düşmüş satır]; hiç parçası kalmayan satır için []."""
    orphans = [span for placement in placements if placement.source is line and not placement.attachments
               for span in placement.spans]
    scripts = tuple(mark for placement in placements for host, mark in placement.attachments if host is line)
    return [replace(TextLine.of(orphans, line.is_code), scripts=scripts)] if orphans else []


class ScriptAttacher:
    """Sayfa satırlarındaki simge parçalarını ev sahibi satırlara bağlar."""

    def __init__(self, lines):
        self._lines = lines

    def attach(self):
        """Ev sahibi bulunan parçalar ev sahibinin simgesi olur ve kendi satırından düşer; bütün
        parçaları düşen satır kaybolur. Önce her parçanın yeri bulunur, sonra satırlar yeniden kurulur."""
        placements = [self._placement(line, run) for line in self._lines for run in self._runs(line)]
        return [kept for line in self._lines for kept in _kept(line, placements)]

    def _placement(self, line, run):
        part = TextLine.of(run, line.is_code)
        candidates = ((host, self._marker(part, host)) for host in self._lines if host is not line)
        attachments = ((host, ScriptMark(part, marker)) for host, marker in candidates if marker)
        return _Placement(line, run, tuple(islice(attachments, 1)))

    @staticmethod
    def _runs(line):
        """Aynı taban çizgisindeki uzak parçalar ayrı simgelerdir: bir cümlede iki
        ayrı üst simge ('cᵉ ... cᵃ') tek parça gibi gelir."""
        runs = [[line.spans[0]]]
        for span in line.spans[1:]:
            if span.box.x0 - runs[-1][-1].box.x1 > SCRIPT_RUN_MAX_GAP:
                runs.append([span])
            else:
                runs[-1].append(span)
        return runs

    def _marker(self, part, host):
        """part, host satırının üst simgesiyse '^', alt simgesiyse '_'; değilse boş.
        Simgenin fontu ev sahibininkinden farklı olabilir."""
        if not self._is_script_sized(part, host) or not self._is_placed(part, host):
            return ""
        shift = host.baseline - part.baseline
        threshold = host.size * SCRIPT_SHIFT_RATIO
        if abs(shift) > host.size:
            return ""
        if shift > threshold:
            return "^"
        return "_" if -shift > threshold else ""

    @staticmethod
    def _is_script_sized(part, host):
        """Kod satırında her küçük parça simge sayılır; gövde metninde dipnot
        işaretini (çok daha küçük punto) dışarıda bırakmak için alt sınır vardır."""
        ratio = part.size / host.size
        if host.is_code:
            return ratio < SCRIPT_SIZE_RATIO
        return PROSE_SCRIPT_MIN_SIZE_RATIO <= ratio < SCRIPT_SIZE_RATIO

    @staticmethod
    def _is_placed(part, host):
        """Kod satırında simge satırın sağ ucuna kadar herhangi bir yerde olabilir;
        gövde metninde cümlenin ortasında, sembolün hemen sağındadır ('mᵃ'). Sözcük
        ya da cümle sonundaki küçük işaret ('Photos.²²') dipnot göndermesidir."""
        if host.is_code:
            return host.box.x0 <= part.box.x0 <= host.box.x1 + char_width(host)
        touches = any(abs(span.box.x1 - part.box.x0) <= PROSE_SCRIPT_MAX_GAP for span in host.spans)
        token = _word_before(host, part.box.x0)
        return touches and 0 < len(token) <= PROSE_SCRIPT_MAX_HOST_CHARS and token.isalnum()


class ScriptFixes:
    """Bağlanmış simgelerden ODL metnine uygulanacak {düz: simgeli} eşlemeleri."""

    def __init__(self, lines):
        self._lines = lines

    def for_code(self):
        """Düz metne düşürülen simgeli kod parçaları ('3.14 × 10' -> '3.14 × 10^23');
        TextFixer.plain uygular."""
        return {line.raw_text.strip(): line.text.strip()
                for line in self._lines if not line.is_code and uses_script_layout(line)}

    def for_prose(self):
        """Gövde metnindeki simgeli sözcükler ('ma' -> 'mᵃ')."""
        return {plain: scripted for line in self._lines if not uses_script_layout(line)
                for mark in line.scripts for plain, scripted in mark.word_fix(line).items()}
