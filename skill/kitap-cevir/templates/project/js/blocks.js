// Sayfa bloklarını (tools/FORMAT.md) HTML'e çevirir.
const Blocks = (function () {
  const escapeHtml = Highlight.escapeHtml;
  const LISTING_CAPTION = /^(Listing \d+-\d+(?: \(continued\))?)[:\s/]*(.*)$/;

  function inlineCode(text) {
    return escapeHtml(text).replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  function unitHtml(unit, field) {
    const value = unit[field] || "";
    return unit.html ? value : inlineCode(value);
  }

  // only: "en" | "tr" | null — tek dilli yaprak için yalnız o taraf üretilir (yoksa diğerine düşer).
  function pair(unit, only) {
    if (only) {
      const field = unit[only] ? only : (only === "en" ? "tr" : "en");
      return `<span class="${only}-text">${unitHtml(unit, field)}</span>`;
    }
    return `<span class="en-text">${unitHtml(unit, "en")}</span>` +
           `<span class="tr-text">${unitHtml(unit, "tr")}</span>`;
  }

  function wordSpan(word) {
    return `<span class="word" data-t="${escapeHtml(word.t)}">${escapeHtml(word.w)}</span>`;
  }

  function wordsHtml(sentence) {
    const text = sentence.en;
    let cursor = 0, html = "";
    sentence.words.forEach((word) => {
      const found = text.indexOf(word.w, cursor);
      if (found === -1) return;
      html += escapeHtml(text.slice(cursor, found)) + wordSpan(word);
      cursor = found + word.w.length;
    });
    return html + escapeHtml(text.slice(cursor));
  }

  function sentenceHtml(sentence, sid, only) {
    const hasWords = sentence.words && sentence.words.length;
    const en = hasWords ? wordsHtml(sentence) : unitHtml(sentence, "en");
    const enSpan = `<span class="en-text">${en}</span>`;
    const trSpan = `<span class="tr-text">${unitHtml(sentence, "tr")}</span>`;
    const inner = only === "en" ? enSpan : only === "tr" ? pair(sentence, "tr") : enSpan + trSpan;
    return `<span class="sentence" data-sid="${sid}">${inner}</span>`;
  }

  function paraClasses(block) {
    const classes = ["para"];
    if (block.style) classes.push(block.style);
    if (block.sentences.some((s) => s.html)) classes.push("legacy-para");
    return classes.join(" ");
  }

  function renderPara(block, ctx) {
    const body = block.sentences.map((s, i) => sentenceHtml(s, `${ctx.index}-${i}`, ctx.only)).join(" ");
    return `<p class="${paraClasses(block)}">${body}</p>`;
  }

  function renderChapter(block, ctx) {
    const num = block.num ? `<div class="chapter-num">${block.num}</div>` : "";
    const author = block.author ? `<div class="chapter-author">${escapeHtml(block.author)}</div>` : "";
    return `<header class="chapter-opener">${num}<h1 class="chapter-title">${pair(block, ctx.only)}</h1>${author}</header>`;
  }

  function renderHeading(block, ctx) {
    const level = Math.min(Math.max(block.level || 1, 1), 3);
    const tag = `h${level + 1}`;
    return `<${tag} class="heading level-${level}">${pair(block, ctx.only)}</${tag}>`;
  }

  function renderList(block, ctx) {
    const tag = block.ordered ? "ol" : "ul";
    const items = block.items.map((item, i) =>
      `<li class="sentence" data-sid="${ctx.index}-${i}">${pair(item, ctx.only)}</li>`).join("");
    return `<${tag} class="list">${items}</${tag}>`;
  }

  function captionInner(text) {
    const match = LISTING_CAPTION.exec(text || "");
    if (!match) return escapeHtml(text || "");
    return `<span class="listing-label">${escapeHtml(match[1])}</span> ` +
           `<span class="listing-file">${escapeHtml(match[2])}</span>`;
  }

  function listingCaption(caption, only) {
    if (!caption) return "";
    const unit = { en: captionInner(caption.en), tr: captionInner(caption.tr || caption.en), html: true };
    return `<figcaption class="listing-caption ui-pair">${pair(unit, only)}</figcaption>`;
  }

  function renderCode(block, ctx, caption) {
    const code = Highlight.render(block.code || "", block.lang);
    return `<figure class="listing">${listingCaption(caption || block.caption, ctx.only)}` +
           `<pre class="code"><code>${code}</code></pre></figure>`;
  }

  function renderImage(block, ctx) {
    const src = `data/pages/${ctx.pageId}_images/${encodeURIComponent(block.src)}`;
    return `<figure class="figure"><img src="${src}" alt="" loading="lazy"></figure>`;
  }

  function renderUnit(block, ctx, tag, cls) {
    return `<${tag} class="${cls} sentence" data-sid="${ctx.index}-0">${pair(block, ctx.only)}</${tag}>`;
  }

  function renderTable(block, ctx) {
    const rows = block.rows.map((row, r) => `<tr>${row.map((cell, c) =>
      `<td class="sentence" data-sid="${ctx.index}-${r}-${c}">${pair(cell, ctx.only)}</td>`).join("")}</tr>`).join("");
    return `<table class="book-table">${rows}</table>`;
  }

  function renderOne(block, ctx, next) {
    switch (block.type) {
      case "chapter": return renderChapter(block, ctx);
      case "heading": return renderHeading(block, ctx);
      case "para": return renderPara(block, ctx);
      case "list": return renderList(block, ctx);
      case "code": return renderCode(block, ctx);
      case "caption": return next && next.type === "code" && block.kind === "listing" ? "" : renderUnit(block, ctx, "p", "caption");
      case "image": return renderImage(block, ctx);
      case "footnote": return renderUnit(block, ctx, "div", "footnote");
      case "table": return renderTable(block, ctx);
      case "html": return `<div class="legacy">${block.html}</div>`;
      default: return "";
    }
  }

  function withListingCaptions(blocks, pageId, only) {
    return blocks.map((block, index) => {
      const ctx = { pageId, only, index };
      const previous = blocks[index - 1];
      const hasCaption = previous && previous.type === "caption" && previous.kind === "listing";
      if (block.type === "code" && hasCaption) return renderCode(block, ctx, previous);
      return renderOne(block, ctx, blocks[index + 1]);
    });
  }

  function groupFootnotes(html) {
    return html.replace(/(<div class="footnote sentence">[\s\S]*?<\/div>\s*)+/g, (group) =>
      `<aside class="footnotes">${group}</aside>`);
  }

  function markDropcap(html, blocks) {
    if (!blocks.length || blocks[0].type !== "chapter") return html;
    return html.replace('<p class="para">', '<p class="para dropcap">');
  }

  function render(page, only) {
    const html = withListingCaptions(page.blocks || [], page.id, only || null).join("\n");
    return markDropcap(groupFootnotes(html), page.blocks || []);
  }

  return { render, pair, inlineCode, escapeHtml };
})();
