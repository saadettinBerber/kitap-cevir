// Küçük söz dizimi renklendirici (Java / Python / JavaScript).
// Girdi düz metindir; çıktı HTML'dir (karakterler kaçırılır).
const Highlight = (function () {
  const KEYWORDS = {
    java: "abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while var record yield sealed permits null true false",
    python: "and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield None True False self",
    javascript: "async await break case catch class const continue debugger default delete do else export extends finally for function if import in instanceof let new of return static super switch this throw try typeof var void while with yield null undefined true false",
  };
  const ALIASES = { js: "javascript", py: "python", ts: "javascript", typescript: "javascript" };
  const COMMENT_PATTERNS = {
    python: "#[^\\n]*|\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''",
    default: "\\/\\/[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/",
  };
  const STRING = "\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*'|`(?:\\\\.|[^`\\\\])*`";
  const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };

  function escapeHtml(text) {
    return String(text).replace(/[&<>"]/g, (ch) => ESCAPES[ch]);
  }

  function languageOf(lang) {
    const key = (lang || "java").toLowerCase();
    return KEYWORDS[ALIASES[key] || key] ? (ALIASES[key] || key) : "java";
  }

  function tokenizer(language) {
    const comment = COMMENT_PATTERNS[language] || COMMENT_PATTERNS.default;
    return new RegExp(
      `(${comment})|(${STRING})|(@\\w+)|(\\b\\d+(?:\\.\\d+)?[fFLd]?\\b)|(\\b[A-Z][\\w$]*\\b)|([a-z_$][\\w$]*)(?=\\s*\\()|(\\b[a-z_][\\w$]*\\b)`,
      "g"
    );
  }

  function classify(match, keywords) {
    if (match[1]) return "comment";
    if (match[2]) return "str";
    if (match[3]) return "ann";
    if (match[4]) return "num";
    if (match[5]) return "type";
    if (match[6]) return keywords.has(match[6]) ? "kw" : "method";
    if (match[7]) return keywords.has(match[7]) ? "kw" : null;
    return null;
  }

  function render(code, lang) {
    const language = languageOf(lang);
    const keywords = new Set(KEYWORDS[language].split(" "));
    const pattern = tokenizer(language);
    let html = "", cursor = 0, match;
    while ((match = pattern.exec(code)) !== null) {
      html += escapeHtml(code.slice(cursor, match.index));
      const cls = classify(match, keywords);
      html += cls ? `<span class="${cls}">${escapeHtml(match[0])}</span>` : escapeHtml(match[0]);
      cursor = match.index + match[0].length;
    }
    return html + escapeHtml(code.slice(cursor));
  }

  return { render, escapeHtml };
})();
