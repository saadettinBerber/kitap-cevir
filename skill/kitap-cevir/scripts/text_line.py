"""PDF'teki tek bir taban çizgisinin parçaları (PyMuPDF span'ları): kod mu düz
metin mi, kendisine bağlanmış alt/üst simgeler ve çıkarımda kullanılacak metni.
Koordinatlar üst orijinlidir.
"""
MONO_CHAR_WIDTH_RATIO = 0.6       # tek aralıklı karakter genişliği / punto
SAME_BASELINE_TOLERANCE = 2.0     # bu kadar yakın taban çizgisi = aynı satır
MIN_STANDALONE_CODE_CHARS = 12    # düz metinle aynı satırdaki kod parçası bundan kısaysa satır içi koddur


class TextLine:
    """Bir satırın span'ları; `scripts` ev sahibi satıra bağlanmış simgelerdir."""

    def __init__(self, spans, is_code):
        self.spans = spans
        self.is_code = is_code
        self.scripts = []
        self.baseline = spans[0]["origin"][1]
        self.bbox = [min(sp["bbox"][0] for sp in spans), min(sp["bbox"][1] for sp in spans),
                     max(sp["bbox"][2] for sp in spans), max(sp["bbox"][3] for sp in spans)]
        self.text = ""

    @classmethod
    def of_spans(cls, spans):
        return cls(spans, is_code=all(span["is_code"] for span in spans))

    @staticmethod
    def join(spans):
        """Baştaki boşluklar korunur: PDF'te kod girintisi metnin içindedir."""
        return "".join(span["text"] for span in spans).rstrip()

    @property
    def left(self):
        return self.bbox[0]

    @property
    def top(self):
        return self.bbox[1]

    @property
    def right(self):
        return self.bbox[2]

    @property
    def bottom(self):
        return self.bbox[3]

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def size(self):
        return self.spans[0]["size"]

    @property
    def char_width(self):
        return self.size * MONO_CHAR_WIDTH_RATIO

    @property
    def raw_text(self):
        return self.join(self.spans)

    def sort_key(self):
        return round(self.top), self.left

    def is_level_with(self, other):
        return abs(self.baseline - other.baseline) <= SAME_BASELINE_TOLERANCE

    def continues_code(self, other):
        """Aynı taban çizgisindeki iki kod parçası tek kod satırıdır."""
        return self.is_code and other.is_code and self.is_level_with(other)

    def absorb(self, other):
        self.spans = sorted(self.spans + other.spans, key=lambda sp: sp["bbox"][0])
        self.scripts += other.scripts
        self.bbox = [min(self.left, other.left), min(self.top, other.top),
                     max(self.right, other.right), max(self.bottom, other.bottom)]

    def split_leading_code(self):
        """'formül , or ...' gibi kod ile başlayıp düz metinle süren satırı ikiye
        ayırır; kod parçası kod satırlarıyla birleşebilsin diye. Tek harflik
        baş parça ('W be the key...') satır içi koddur, bölünmez."""
        if self.is_code or not self.spans[0]["is_code"]:
            return [self]
        split = next(i for i, span in enumerate(self.spans) if not span["is_code"])
        if len(self.join(self.spans[:split]).strip()) < MIN_STANDALONE_CODE_CHARS:
            return [self]
        return [TextLine(self.spans[:split], is_code=True), TextLine(self.spans[split:], is_code=False)]

    def is_standalone_code(self):
        return len(self.raw_text.strip()) >= MIN_STANDALONE_CODE_CHARS

    def word_before(self, x0, tolerance):
        """x0 konumunun solunda kalan son sözcük."""
        head = "".join(span["text"] for span in self.spans if span["bbox"][2] <= x0 + tolerance).split()
        return head[-1] if head else ""

    def uses_script_layout(self):
        """Kod satırı ve kod formülü içeren satır boşlukla dizilir; gövde metninin
        simgesi satır metnine değil yalnız sözcük düzeltmesine gider."""
        return self.is_code or bool(self.scripts and any(span["is_code"] for span in self.spans))

    def render(self):
        self.text = self._spaced_text() if self.uses_script_layout() else self.raw_text

    def _spaced_text(self):
        """Parçaları x konumuna göre boşlukla dizer; alt/üst simgeleri araya koyar."""
        pieces = [(sp["bbox"][0], sp["bbox"][2], sp["text"], False) for sp in self.spans]
        pieces += [(mark.x0, mark.x1, mark.text, True) for mark in self.scripts]
        text, cursor, after_script = "", None, False
        for x0, x1, piece, is_script in sorted(pieces):
            threshold = self.char_width if after_script else self.char_width / 2
            if cursor is not None and x0 - cursor > threshold:
                text += " " * max(1, round((x0 - cursor) / self.char_width))
            text += piece
            cursor = x1 if cursor is None else max(cursor, x1)
            after_script = is_script
        return text.rstrip()
