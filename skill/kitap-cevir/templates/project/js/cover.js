// Kapak görünümü: kitap bilgisi, çeviri ilerlemesi ve bölüm listesi.
const Cover = (function () {
  const escapeHtml = Highlight.escapeHtml;

  function translatedCount(toc, chapter) {
    return Object.keys(toc.pages).map(Number)
      .filter((n) => n >= chapter.start && n <= chapter.end && !toc.pages[n].blank).length;
  }

  function firstTranslated(toc, chapter) {
    const pages = Object.keys(toc.pages).map(Number)
      .filter((n) => n >= chapter.start && n <= chapter.end && !toc.pages[n].blank);
    return pages.length ? Math.min(...pages) : null;
  }

  function chapterRow(toc, chapter) {
    const count = translatedCount(toc, chapter);
    const first = firstTranslated(toc, chapter);
    const status = count ? `${count} sayfa çevrildi` : "henüz çevrilmedi";
    return `<button class="cover-ch${count ? "" : " empty"}" ${first ? `data-page="${first}"` : "disabled"}>` +
      `<span class="n">${chapter.num}</span><span>${escapeHtml(chapter.tr)}<small>${escapeHtml(chapter.en)} · s. ${chapter.start} · ${status}</small></span></button>`;
  }

  function progressHtml(toc) {
    const done = Object.values(toc.pages).filter((p) => !p.blank).length;
    const percent = Math.round((done / toc.bookTotalPages) * 100);
    return `<div class="cover-progress"><div class="cover-bar"><span style="width:${percent}%"></span></div>` +
      `${done} / ${toc.bookTotalPages} sayfa çevrildi (%${percent})</div>`;
  }

  function actions(lastRead) {
    const resume = lastRead ? `<button class="ui-btn primary" data-page="${lastRead}">Kaldığım yerden devam et · Sayfa ${lastRead}</button>` : "";
    return `<div class="cover-actions">${resume}<button class="ui-btn" data-page="1">Baştan başla</button></div>`;
  }

  function optional(className, text) {
    return text ? `<div class="${className}">${escapeHtml(text)}</div>` : "";
  }

  function subtitleTr(book) {
    const suffix = "İngilizce/Türkçe interaktif okuma";
    return book.subtitleTr ? `${book.subtitleTr} — ${suffix}` : suffix;
  }

  function header(book) {
    return optional("cover-series", book.series) +
      `<h1 class="cover-title">${escapeHtml(book.title || "")}</h1>` +
      optional("cover-sub", book.subtitle) +
      optional("cover-sub-tr", subtitleTr(book)) +
      optional("cover-author", book.author) + `<div class="cover-rule"></div>`;
  }

  function render(toc, lastRead) {
    return `<div class="cover">` + header(toc.book || {}) +
      progressHtml(toc) + actions(lastRead) +
      `<div class="cover-chapters">${toc.chapters.map((ch) => chapterRow(toc, ch)).join("")}</div></div>`;
  }

  return { render };
})();
