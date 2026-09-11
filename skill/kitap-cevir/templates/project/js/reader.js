// Okuyucu motoru: görünüm (tek / çift sayfa), gezinme ve adres çubuğu yönlendirmesi.
// data/toc.js -> window.TOC, sayfa verisi -> Pages.load(N)
const Reader = (function () {
  const LAST_PAGE_KEY = Prefs.key("last-page");
  const LAYOUT_KEY = Prefs.key("layout");
  const SPREAD_MIN_WIDTH = 1000;
  const state = { page: null, layout: "single", direction: "next" };

  function toc() { return window.TOC; }
  function book() { return toc().book || {}; }
  function pageInfo(num) { return toc().pages[num]; }
  function isTranslated(num) { return Boolean(pageInfo(num)) && !pageInfo(num).blank; }
  function isBlank(num) { return Boolean(pageInfo(num)) && pageInfo(num).blank; }
  function inBook(num) { return Number.isInteger(num) && num >= 1 && num <= toc().bookTotalPages; }
  function hashOf(num) { return num === "cover" ? "#cover" : `#page-${num}`; }
  function sheets() { return [document.getElementById("sheet-left"), document.getElementById("sheet-right")]; }

  function untranslatedMessage(num) {
    return `Sayfa ${num} henüz çevrilmedi. '/kitap-cevir ${num}' yazın veya 'sıradaki sayfa' deyin.`;
  }

  /* ---------- Görünüm kipi ---------- */
  function isSpread() { return state.layout === "spread" && window.innerWidth >= SPREAD_MIN_WIDTH; }
  function isParallel() { return isSpread() && Controls.currentLang() === "both"; }

  function pairOf(num) {
    if (isParallel()) return [num, num];
    const left = num % 2 === 0 ? num : num - 1;
    return [left, left + 1];
  }

  function pairHasContent(num) {
    return pairOf(num).some((n) => inBook(n) && isTranslated(n));
  }

  function canShow(num) {
    return isSpread() && !isParallel() ? pairHasContent(num) : isTranslated(num);
  }

  /* ---------- Çizim ---------- */
  function renderOne(sheet, num, side) {
    if (!inBook(num)) return Sheet.renderPlaceholder(sheet, num, "empty");
    if (isBlank(num)) return Sheet.renderPlaceholder(sheet, num, "blank");
    if (!isTranslated(num)) return Sheet.renderPlaceholder(sheet, num, "untranslated");
    return Pages.load(num).then((page) => Sheet.render(sheet, page, side));
  }

  function renderSpread(num) {
    const [left, right] = sheets();
    const [leftNum, rightNum] = pairOf(num);
    if (isParallel()) {
      document.documentElement.dataset.lang = "parallel";
      return Promise.all([renderOne(left, leftNum, { only: "en", side: "left" }),
                          renderOne(right, rightNum, { only: "tr", side: "right" })]);
    }
    return Promise.all([renderOne(left, leftNum, { side: "left" }), renderOne(right, rightNum, { side: "right" })]);
  }

  function renderCover() {
    const [left, right] = sheets();
    const lastRead = Number(localStorage.getItem(LAST_PAGE_KEY)) || null;
    if (isSpread()) Sheet.renderPlaceholder(left, "", "empty");
    Sheet.renderCover(isSpread() ? right : left, toc(), isTranslated(lastRead) ? lastRead : null);
    document.getElementById("crumb").textContent = `${book().author || ""} · İngilizce–Türkçe`;
    document.title = `${book().title} TR — Kapak`;
  }

  function breadcrumb(page) {
    const chapter = page.chapter || {};
    const section = page.section || {};
    const tail = section.tr || section.en ? ` › <span class="en-text">${Blocks.escapeHtml(section.en || section.tr)}</span>` +
      `<span class="tr-text">${Blocks.escapeHtml(section.tr || section.en)}</span>` : "";
    return `<span class="en-text">Chapter ${chapter.num} · ${Blocks.escapeHtml(chapter.en || "")}</span>` +
           `<span class="tr-text">Bölüm ${chapter.num} · ${Blocks.escapeHtml(chapter.tr || "")}</span>${tail}`;
  }

  function renderCurrent() {
    const book = document.getElementById("book");
    book.classList.toggle("spread", isSpread());
    sheets()[1].hidden = !isSpread();
    Controls.applyLang();
    const work = state.page === "cover" ? Promise.resolve(renderCover())
      : renderSpread(state.page).then(function () {
          var anchor = canShow(state.page) && isTranslated(state.page) ? state.page : pairOf(state.page).find(isTranslated);
          return anchor ? Pages.load(anchor) : null;
        }).then(function (page) {
          if (page) { document.getElementById("crumb").innerHTML = breadcrumb(page); document.title = `${book().title} TR — Sayfa ${state.page}`; }
        });
    return work.then(finishRender).catch(function (error) { Panels.toast(error.message); });
  }

  function animateBook() {
    if (typeof Flip !== "undefined" && Flip.prefersReduced()) return;
    const book = document.getElementById("book");
    book.classList.remove("turn-next", "turn-prev");
    void book.offsetWidth;
    book.classList.add(state.direction === "prev" ? "turn-prev" : "turn-next");
  }

  function finishRender() {
    const num = state.page;
    document.getElementById("page-input").value = num === "cover" ? "" : num;
    updateTurnButtons();
    Panels.buildToc(toc(), num);
    animateBook();
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (num !== "cover") localStorage.setItem(LAST_PAGE_KEY, String(num));
    if (location.hash !== hashOf(num)) history.replaceState(null, "", hashOf(num));
  }

  /* ---------- Gezinme ---------- */
  function nextAnchor(from, step) {
    if (isSpread() && !isParallel()) return step > 0 ? pairOf(from)[1] + 1 : pairOf(from)[0] - 1;
    let num = from + step;
    while (isBlank(num)) num += step;
    return num;
  }

  function goTo(target, direction) {
    state.direction = direction || "next";
    if (target === "cover") { state.page = "cover"; renderCurrent(); return true; }
    const num = Number(target);
    if (!inBook(num)) { Panels.toast("Geçersiz sayfa numarası."); return false; }
    if (!canShow(num)) { Panels.toast(untranslatedMessage(num)); return false; }
    state.page = num;
    renderCurrent();
    return true;
  }

  function goNext() {
    const from = state.page === "cover" ? 0 : state.page;
    goTo(nextAnchor(from, 1), "next");
  }

  function goPrev() {
    if (state.page === "cover") return;
    const target = nextAnchor(state.page, -1);
    goTo(target < 1 ? "cover" : target, "prev");
  }

  function updateTurnButtons() {
    const atCover = state.page === "cover";
    const next = nextAnchor(atCover ? 0 : state.page, 1);
    document.querySelectorAll("[data-nav='prev']").forEach((b) => { b.disabled = atCover; });
    document.querySelectorAll("[data-nav='next']").forEach((b) => { b.disabled = !inBook(next) || !canShow(next); });
    const label = document.getElementById("pager-label");
    if (label) label.textContent = atCover ? "Kapak" : `Sayfa ${state.page} / ${toc().bookTotalPages}`;
  }

  function setLayout(layout) {
    state.layout = layout === "spread" ? "spread" : "single";
    localStorage.setItem(LAYOUT_KEY, state.layout);
    document.getElementById("layout-btn").classList.toggle("active", state.layout === "spread");
    if (state.page !== null) renderCurrent();
  }

  function toggleLayout() { setLayout(state.layout === "spread" ? "single" : "spread"); }

  function routeFromHash() {
    const match = /^#page-(\d+)$/.exec(location.hash);
    if (match) return goTo(Number(match[1]));
    if (location.hash === "#cover") return goTo("cover");
    const saved = Number(localStorage.getItem(LAST_PAGE_KEY));
    return isTranslated(saved) ? goTo(saved) : goTo("cover");
  }

  function main() {
    if (!window.TOC) { document.querySelector(".page-body").textContent = "data/toc.js yüklenemedi."; return; }
    document.getElementById("page-total").textContent = `/ ${toc().bookTotalPages}`;
    document.querySelector(".brand-title").textContent = `${book().title} — ${book().author}`;
    Panels.init({ onSelectPage: (target) => goTo(target, "next") });
    Concepts.init();
    Controls.init({ goTo, goNext, goPrev, toggleLayout, refresh: renderCurrent, currentPage: () => state.page });
    if (typeof Flip !== "undefined") Flip.init({ onNext: goNext, onPrev: goPrev });
    setLayout(localStorage.getItem(LAYOUT_KEY) || (window.innerWidth >= SPREAD_MIN_WIDTH ? "spread" : "single"));
    window.addEventListener("hashchange", routeFromHash);
    window.addEventListener("resize", Controls.debounce(renderCurrent));
    routeFromHash();
  }

  document.addEventListener("DOMContentLoaded", main);
  return { goTo, goNext, goPrev, setLayout, setLang: (lang) => Controls.setLang(lang) };
})();
