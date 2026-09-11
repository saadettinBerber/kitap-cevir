// Tek bir kitap yaprağını (sheet) doldurur: koşu başlığı, gövde, kavramlar, sayfa numarası.
const Sheet = (function () {
  const escapeHtml = Highlight.escapeHtml;

  function part(sheet, name) { return sheet.querySelector(`.${name}`); }

  function pairText(unit) {
    return `<span class="en-text">${escapeHtml(unit.en || unit.tr || "")}</span>` +
           `<span class="tr-text">${escapeHtml(unit.tr || unit.en || "")}</span>`;
  }

  function chapterLabel(page) {
    const chapter = page.chapter || {};
    return { en: `Chapter ${chapter.num}: ${chapter.en}`, tr: `Bölüm ${chapter.num}: ${chapter.tr}` };
  }

  function runningHead(page, side) {
    const chapterText = chapterLabel(page);
    const hasSection = page.section && (page.section.en || page.section.tr);
    const numberOnLeft = side === "left" || (side !== "right" && page.page % 2 === 0);
    const unit = numberOnLeft ? chapterText : (hasSection ? page.section : chapterText);
    const text = `<span class="head-text">${pairText(unit)}</span>`;
    const num = `<span class="folio-num">${page.page}</span>`;
    return numberOnLeft ? num + text : text + num;
  }

  function render(sheet, page, options) {
    const only = options.only || null;
    sheet.className = `sheet ${options.side || ""}`.trim();
    if (only) sheet.dataset.lang = only; else delete sheet.dataset.lang;
    part(sheet, "running-head").innerHTML = runningHead(page, options.side);
    part(sheet, "page-body").innerHTML = Blocks.render(page, only);
    part(sheet, "folio").innerHTML = `<b>${page.page}</b><small>PDF sayfa ${page.pdf_page}</small>`;
    Concepts.renderButtons(part(sheet, "concepts"), page.concepts, page.page);
  }

  function placeholderText(num, reason) {
    if (reason === "blank") return `<span class="ph-num">${num}</span><span>Bu sayfa kitapta boştur.</span>`;
    if (reason === "untranslated") {
      return `<span class="ph-num">${num}</span><span>Henüz çevrilmedi.<br><small>'/kitap-cevir ${num}' yazın veya 'sıradaki sayfa' deyin.</small></span>`;
    }
    return "";
  }

  function renderPlaceholder(sheet, num, reason) {
    sheet.className = "sheet placeholder";
    delete sheet.dataset.lang;
    part(sheet, "running-head").innerHTML = "";
    part(sheet, "page-body").innerHTML = `<div class="placeholder-body">${placeholderText(num, reason)}</div>`;
    part(sheet, "folio").innerHTML = reason === "empty" ? "" : `<b>${num}</b>`;
    Concepts.renderButtons(part(sheet, "concepts"), [], null);
  }

  function renderCover(sheet, toc, lastRead) {
    sheet.className = "sheet cover-sheet";
    delete sheet.dataset.lang;
    part(sheet, "running-head").innerHTML = "";
    part(sheet, "page-body").innerHTML = Cover.render(toc, lastRead);
    part(sheet, "folio").innerHTML = "";
    Concepts.renderButtons(part(sheet, "concepts"), [], null);
  }

  return { render, renderPlaceholder, renderCover };
})();
