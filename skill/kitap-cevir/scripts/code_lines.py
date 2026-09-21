"""PyMuPDF satırlarını kod çıkarımı için hazırlar: geniş boşlukta bölünen
parçaları aynı taban çizgisinde birleştirir, kod formüllerindeki alt/üst
simgeleri ('10' üstünde '23') ev sahibi satıra '^23' / '_K' olarak bağlar,
kod ile başlayıp düz metinle süren satırı ikiye ayırır.
"""
MONO_CHAR_WIDTH_RATIO = 0.6       # tek aralıklı karakter genişliği / punto
SAME_BASELINE_TOLERANCE = 2.0     # bu kadar yakın taban çizgisi = aynı satır
SCRIPT_SIZE_RATIO = 0.85          # ev sahibi puntosunun altındaki kaydırılmış parça = alt/üst simge
SCRIPT_SHIFT_RATIO = 0.12         # taban çizgisi kayması / punto: bunun üstü üst (^) ya da alt (_) simge
MIN_STANDALONE_CODE_CHARS = 12    # düz metinle aynı satırdaki kod parçası bundan kısaysa satır içi koddur
PROSE_SCRIPT_MIN_SIZE_RATIO = 0.7 # gövde metninde bundan küçük parça dipnot işaretidir, simge değil
PROSE_SCRIPT_MAX_GAP = 1.5        # simge, ev sahibi parçanın sağ kenarına bu kadar yakın başlar
SCRIPT_RUN_MAX_GAP = 2.0          # aynı taban çizgisinde bu kadar uzak parçalar ayrı simgelerdir
PROSE_SCRIPT_MAX_HOST_CHARS = 2   # gövde metninde simge sembole yapışır; uzun sözcüğünki dipnot göndermesidir

SUPERSCRIPTS = str.maketrans("0123456789abcdefghijklmnoprstuvwxyz+-=()",
                             "⁰¹²³⁴⁵⁶⁷⁸⁹ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ⁺⁻⁼⁽⁾")
SUBSCRIPTS = str.maketrans("0123456789aehijklmnoprstuvx+-=()",
                           "₀₁₂₃₄₅₆₇₈₉ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ₊₋₌₍₎")


def line_spans(line, code_font):
    spans = [span for span in line["spans"] if span["text"].strip()]
    for span in spans:
        span["is_code"] = code_font.matches(span)
    return spans


def line_text(spans):
    """Baştaki boşluklar korunur: PDF'te kod girintisi metnin içindedir."""
    return "".join(span["text"] for span in spans).rstrip()


def _split_by_baseline(spans):
    """PyMuPDF bazen üst simgeyi aynı satıra koyar; farklı taban çizgisindeki
    parçalar ayrı satır olur ki simge bağlama tek yoldan çalışsın. Yarım
    puntoluk font farkları (italik vb.) aynı taban çizgisi sayılır."""
    groups = []
    for span in sorted(spans, key=lambda sp: sp["origin"][1]):
        if groups and abs(span["origin"][1] - groups[-1][0]["origin"][1]) <= SAME_BASELINE_TOLERANCE:
            groups[-1].append(span)
        else:
            groups.append([span])
    return [sorted(group, key=lambda sp: sp["bbox"][0]) for group in groups]


def _raw_lines(page, code_font):
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for spans in _split_by_baseline(line_spans(line, code_font)):
                lines.append(_line_of(spans, is_code=all(span["is_code"] for span in spans)))
    lines.sort(key=lambda ln: (round(ln["bbox"][1]), ln["bbox"][0]))
    return lines


def _line_of(spans, is_code):
    bbox = [min(sp["bbox"][0] for sp in spans), min(sp["bbox"][1] for sp in spans),
            max(sp["bbox"][2] for sp in spans), max(sp["bbox"][3] for sp in spans)]
    return {"spans": spans, "bbox": bbox, "scripts": [], "is_code": is_code,
            "baseline": spans[0]["origin"][1]}


def _split_leading_code(line):
    """'formül , or ...' gibi kod ile başlayıp düz metinle süren satırı ikiye
    ayırır; kod parçası kod satırlarıyla birleşebilsin diye. Tek harflik
    baş parça ('W be the key...') satır içi koddur, bölünmez."""
    spans = line["spans"]
    if line["is_code"] or not spans[0]["is_code"]:
        return [line]
    split = next(i for i, sp in enumerate(spans) if not sp["is_code"])
    if len(line_text(spans[:split]).strip()) < MIN_STANDALONE_CODE_CHARS:
        return [line]
    return [_line_of(spans[:split], is_code=True), _line_of(spans[split:], is_code=False)]


def _same_baseline(first, second):
    return (first["is_code"] and second["is_code"]
            and abs(first["baseline"] - second["baseline"]) <= SAME_BASELINE_TOLERANCE)


def _absorb(host, line):
    host["spans"] = sorted(host["spans"] + line["spans"], key=lambda sp: sp["bbox"][0])
    host["scripts"] += line["scripts"]
    host["bbox"] = [min(host["bbox"][0], line["bbox"][0]), min(host["bbox"][1], line["bbox"][1]),
                    max(host["bbox"][2], line["bbox"][2]), max(host["bbox"][3], line["bbox"][3])]


def _merge_same_baseline(lines):
    merged = []
    for line in lines:
        if merged and _same_baseline(merged[-1], line):
            _absorb(merged[-1], line)
        else:
            merged.append(line)
    return merged


def _script_sized(line, host_size, is_code_host):
    """Kod satırında her küçük parça simge sayılır; gövde metninde dipnot
    işaretini (çok daha küçük punto) dışarıda bırakmak için alt sınır vardır."""
    ratio = line["spans"][0]["size"] / host_size
    if is_code_host:
        return ratio < SCRIPT_SIZE_RATIO
    return PROSE_SCRIPT_MIN_SIZE_RATIO <= ratio < SCRIPT_SIZE_RATIO


def _host_token(line, x0):
    """Verilen x konumunun solunda kalan son sözcük."""
    head = "".join(span["text"] for span in line["spans"]
                   if span["bbox"][2] <= x0 + PROSE_SCRIPT_MAX_GAP).split()
    return head[-1] if head else ""


def _is_prose_script(line, host):
    """Gövde metninde simge bir sembole yapışır ('mᵃ'): ev sahibi parça simgenin
    başladığı yerde biter ve kısa bir semboldür. Sözcüğün ya da cümlenin
    sonundaki küçük işaret ('Photos.²²') dipnot göndermesidir, simge değil."""
    touches = any(abs(span["bbox"][2] - line["bbox"][0]) <= PROSE_SCRIPT_MAX_GAP
                  for span in host["spans"])
    token = _host_token(host, line["bbox"][0])
    return touches and 0 < len(token) <= PROSE_SCRIPT_MAX_HOST_CHARS and token.isalnum()


def _script_placed(line, host, host_size):
    """Kod satırında simge satırın sağ ucuna kadar herhangi bir yerde olabilir;
    gövde metninde cümlenin ortasında, sembolün hemen sağındadır."""
    if host["is_code"]:
        reach = host["bbox"][2] + host_size * MONO_CHAR_WIDTH_RATIO
        return host["bbox"][0] <= line["bbox"][0] <= reach
    return _is_prose_script(line, host)


def _script_marker(line, host):
    """line, host satırının üst simgesiyse '^', alt simgesiyse '_' verir;
    değilse boş. Simgenin fontu ev sahibininkinden farklı olabilir."""
    host_size = host["spans"][0]["size"]
    if not _script_sized(line, host_size, host["is_code"]) or not _script_placed(line, host, host_size):
        return ""
    shift = host["baseline"] - line["baseline"]
    if abs(shift) > host_size:
        return ""
    return "^" if shift > host_size * SCRIPT_SHIFT_RATIO else "_" if -shift > host_size * SCRIPT_SHIFT_RATIO else ""


def _script_runs(line):
    """Aynı taban çizgisindeki uzak parçalar ayrı simgelerdir: bir cümlede iki
    ayrı üst simge ('cᵉ ... cᵃ') tek parça gibi gelir."""
    runs = [[line["spans"][0]]]
    for span in line["spans"][1:]:
        if span["bbox"][0] - runs[-1][-1]["bbox"][2] > SCRIPT_RUN_MAX_GAP:
            runs.append([span])
        else:
            runs[-1].append(span)
    return runs


def _host_of(part, lines, source):
    hosts = ((h, _script_marker(part, h)) for h in lines if h is not source)
    return next(((h, m) for h, m in hosts if m), (None, ""))


def _attach_scripts(lines):
    """Alt/üst simgeler ('10' üstünde '23', cümlede 'mᵃ') ayrı satır gelir;
    ev sahibi satıra x konumuna göre '^23' / '_K' olarak bağlanır."""
    kept = []
    for line in lines:
        orphans, attached = [], 0
        for run in _script_runs(line):
            part = _line_of(run, line["is_code"])
            host, marker = _host_of(part, lines, line)
            if host is None:
                orphans += run
                continue
            attached += 1
            host["scripts"].append({"x0": part["bbox"][0], "x1": part["bbox"][2],
                                    "text": marker + line_text(run).strip()})
        if not attached:
            kept.append(line)
        elif orphans:
            kept.append({**_line_of(orphans, line["is_code"]), "scripts": line["scripts"]})
    return kept


def _spaced_text(line):
    """Parçaları x konumuna göre boşlukla dizer; alt/üst simgeleri araya koyar."""
    char_width = line["spans"][0]["size"] * MONO_CHAR_WIDTH_RATIO
    pieces = [(sp["bbox"][0], sp["bbox"][2], sp["text"], False) for sp in line["spans"]]
    pieces += [(sc["x0"], sc["x1"], sc["text"], True) for sc in line["scripts"]]
    text, cursor, after_script = "", None, False
    for x0, x1, piece, is_script in sorted(pieces):
        threshold = char_width if after_script else char_width / 2
        if cursor is not None and x0 - cursor > threshold:
            text += " " * max(1, round((x0 - cursor) / char_width))
        text += piece
        cursor = x1 if cursor is None else max(cursor, x1)
        after_script = is_script
    return text.rstrip()


def _is_inline_code(line, lines):
    """Düz metinle aynı taban çizgisindeki kod parçası satır içi koddur; yalnız
    satırın en solundaki uzun parça (formül kutusu + ' , or') kod satırı kalır."""
    beside = [other for other in lines if other is not line
              and abs(other["baseline"] - line["baseline"]) <= SAME_BASELINE_TOLERANCE]
    if not any(not other["is_code"] for other in beside):
        return False
    leftmost = all(line["bbox"][0] <= other["bbox"][0] for other in beside)
    return not (leftmost and len(line_text(line["spans"]).strip()) >= MIN_STANDALONE_CODE_CHARS)


def _demote_inline_code(lines):
    for line in lines:
        if line["is_code"] and _is_inline_code(line, lines):
            line["is_code"] = False
    return lines


def uses_script_layout(line):
    """Kod satırı ve kod formülü içeren satır boşlukla dizilir; gövde metninin
    simgesi satır metnine değil yalnız sözcük düzeltmesine gider."""
    return line["is_code"] or bool(line["scripts"] and any(sp["is_code"] for sp in line["spans"]))


def page_lines(page, code_font):
    split = [part for line in _raw_lines(page, code_font) for part in _split_leading_code(line)]
    split.sort(key=lambda ln: (round(ln["bbox"][1]), ln["bbox"][0]))
    lines = _demote_inline_code(_merge_same_baseline(_attach_scripts(split)))
    for line in lines:
        line["text"] = _spaced_text(line) if uses_script_layout(line) else line_text(line["spans"])
    return lines


def script_fixes(lines):
    """Düz metne düşürülen simgeli kod parçaları için {ODL metni: simgeli metin}
    eşlemesi ('3.14 × 10' -> '3.14 × 10^23'); TextFixer.plain uygular."""
    return {line_text(line["spans"]).strip(): line["text"].strip()
            for line in lines if not line["is_code"] and uses_script_layout(line)}


def _as_script(text, marker):
    """Simgeyi Unicode karşılığıyla verir; karşılığı olmayan karakter varsa
    kod tarafındaki '^' / '_' gösterimine düşer."""
    table = SUPERSCRIPTS if marker == "^" else SUBSCRIPTS
    if text and all(ord(char) in table for char in text):
        return text.translate(table)
    return marker + text


def _script_word(line, script):
    """Simgenin solundaki sözcükle simgeyi birleştirir: ODL metninde 'ma' olarak
    duran parçanın düzeltmesi ('ma' -> 'mᵃ')."""
    word = _host_token(line, script["x0"])
    marker, text = script["text"][:1], script["text"][1:]
    if not word or not text:
        return None
    return word + text, word + _as_script(text, marker)


def prose_script_fixes(lines):
    """Gövde metnindeki alt/üst simgeler için {düz sözcük: simgeli sözcük}
    eşlemesi; ODL simgeyi normal karakter olarak düzleştirir."""
    fixes = {}
    for line in lines:
        if uses_script_layout(line):
            continue
        for pair in filter(None, (_script_word(line, s) for s in line["scripts"])):
            fixes[pair[0]] = pair[1]
    return fixes
