// Çekmeceler: İçindekiler ve Sözlük; kısa uyarı (toast).
const Panels = (function () {
  const escapeHtml = Highlight.escapeHtml;
  let onSelectPage = () => {};
  let toastTimer = null;

  function translatedPagesOf(toc, chapter) {
    return Object.keys(toc.pages).map(Number)
      .filter((n) => n >= chapter.start && n <= chapter.end && !toc.pages[n].blank)
      .sort((a, b) => a - b);
  }

  function pageRow(toc, num) {
    const info = toc.pages[num];
    return `<button class="toc-page" data-page="${num}"><span class="pg">${num}</span>` +
      `<span><span class="en-text">${escapeHtml(info.title.en || info.title.tr)}</span>` +
      `<span class="tr-text">${escapeHtml(info.title.tr || info.title.en)}</span></span></button>`;
  }

  function nextUntranslated(toc, chapter, pages) {
    let next = pages.length ? pages[pages.length - 1] + 1 : chapter.start;
    while (toc.pages[next] && toc.pages[next].blank) next += 1;
    return next;
  }

  function gapRow(toc, chapter, pages) {
    const next = nextUntranslated(toc, chapter, pages);
    if (next > chapter.end) return "";
    return `<div class="toc-gap"><span class="en-text">Not translated yet from page ${next} — type "/kitap-cevir ${next}"</span>` +
      `<span class="tr-text">Sayfa ${next} ve sonrası henüz çevrilmedi — "/kitap-cevir ${next}" yazın</span></div>`;
  }

  function chapterGroup(toc, chapter, currentPage) {
    const pages = translatedPagesOf(toc, chapter);
    const isOpen = currentPage >= chapter.start && currentPage <= chapter.end;
    const rows = pages.map((n) => pageRow(toc, n)).join("");
    return `<details class="toc-chapter${pages.length ? "" : " empty"}"${isOpen ? " open" : ""}>` +
      `<summary><span class="ch-num">${chapter.num}</span><span><span class="en-text">${escapeHtml(chapter.en)}</span>` +
      `<span class="tr-text">${escapeHtml(chapter.tr)}</span></span><span class="ch-count">${pages.length} / ${chapter.end - chapter.start + 1}</span></summary>` +
      rows + gapRow(toc, chapter, pages) + `</details>`;
  }

  function buildToc(toc, currentPage) {
    const root = document.getElementById("toc-body");
    root.innerHTML = `<button class="toc-cover" data-page="cover"><span class="en-text">Cover</span><span class="tr-text">Kapak</span></button>` +
      toc.chapters.map((ch) => chapterGroup(toc, ch, currentPage)).join("");
    const current = root.querySelector(`.toc-page[data-page="${currentPage}"]`);
    if (current) current.classList.add("current");
  }

  function glossaryEntry(entry) {
    const note = entry.note ? `<span class="gl-note">${escapeHtml(entry.note)}</span>` : "";
    return `<div class="gl-entry"><b>${escapeHtml(entry.en)}</b><span class="gl-tr">${escapeHtml(entry.tr)}</span>${note}</div>`;
  }

  function renderGlossary(filter) {
    const needle = (filter || "").toLocaleLowerCase("tr");
    const entries = (window.GLOSSARY || []).filter((e) =>
      !needle || `${e.en} ${e.tr} ${e.note}`.toLocaleLowerCase("tr").includes(needle));
    document.getElementById("glossary-body").innerHTML =
      entries.map(glossaryEntry).join("") || `<div class="toc-gap">Sonuç yok</div>`;
  }

  function open(id) {
    close();
    document.getElementById(id).classList.add("open");
    document.getElementById("backdrop").classList.add("open");
  }

  function close() {
    document.querySelectorAll(".drawer.open").forEach((el) => el.classList.remove("open"));
    document.getElementById("backdrop").classList.remove("open");
  }

  function toast(message) {
    const el = document.getElementById("toast");
    el.textContent = message;
    el.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("visible"), 3200);
  }

  function bindToc() {
    document.getElementById("toc-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-page]");
      if (!button) return;
      close();
      onSelectPage(button.dataset.page);
    });
  }

  function bindButtons() {
    document.getElementById("toc-btn").addEventListener("click", () => open("toc-panel"));
    document.getElementById("glossary-btn").addEventListener("click", () => {
      open("glossary-panel");
      document.getElementById("glossary-search").focus();
    });
    document.getElementById("backdrop").addEventListener("click", close);
    document.querySelectorAll(".drawer-close").forEach((b) => b.addEventListener("click", close));
    document.getElementById("glossary-search").addEventListener("input", (e) => renderGlossary(e.target.value));
  }

  function init(handlers) {
    onSelectPage = handlers.onSelectPage;
    bindToc();
    bindButtons();
    renderGlossary("");
  }

  return { init, buildToc, open, close, toast };
})();
