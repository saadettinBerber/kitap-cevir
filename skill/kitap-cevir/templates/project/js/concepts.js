// Kavram kartları: her yaprağın altındaki düğmeler ve ortak modal.
const Concepts = (function () {
  const byPage = {};

  function chip(pageNum, concept, index) {
    return `<button class="chip" data-page="${pageNum}" data-concept="${index}">${Blocks.pair(concept.title)}</button>`;
  }

  function renderButtons(root, concepts, pageNum) {
    const list = concepts || [];
    if (pageNum !== null) byPage[pageNum] = list;
    if (!list.length) { root.innerHTML = ""; return; }
    root.innerHTML = `<h3 class="concepts-title">${label("Concepts on this page", "Bu sayfadaki kavramlar")}</h3>` +
      `<div class="chips">${list.map((c, i) => chip(pageNum, c, i)).join("")}</div>`;
  }

  // Etiketler arayüz metnidir: iki dil kiplerinde yalnız Türkçesi görünür (ui-pair).
  // lang="en": büyük harfe çevrilince "i" Türkçe kurala göre "İ" olmasın.
  function label(en, tr) {
    return `<span class="ui-pair"><span class="en-text" lang="en">${en}</span><span class="tr-text">${tr}</span></span>`;
  }

  // İçerik metni: iki dil kiplerinde İngilizcesinin altında Türkçesi ayrı blok olur.
  function cardText(unit) {
    return `<span class="card-text">${Blocks.pair(unit)}</span>`;
  }

  // Kart türleri (kind): explain, contrast, tradeoff, code — references/FORMAT.md.
  const SIDE_LABELS = {
    code: { bad: ["Before", "Önce"], good: ["After", "Sonra"] },
    contrast: { bad: ["Avoid", "Kaçın"], good: ["Prefer", "Tercih et"] },
  };
  const TIP_LABELS = { tradeoff: ["When to choose", "Ne zaman hangisi"] };
  const DEFAULT_TIP_LABEL = ["Practical tip", "Pratik ipucu"];
  const OPTION_COLUMNS = [["name", "Option", "Seçenek"], ["gains", "Gains", "Kazandırır"],
                          ["costs", "Costs", "Bedeli"]];

  // `kind` alanı olmayan eski kartlarda tür içerikten çıkarılır.
  function kindOf(concept) {
    if (concept.kind) return concept.kind;
    if (concept.options) return "tradeoff";
    const sample = concept.bad || {};
    if (sample.code) return "code";
    return sample.text ? "contrast" : "explain";
  }

  function sampleBody(sample) {
    if (!sample) return "";
    if (sample.code) return `<pre><code>${Highlight.render(sample.code, sample.lang)}</code></pre>`;
    if (sample.text) return `<p class="sample-text">${cardText(sample.text)}</p>`;
    return "";
  }

  function example(concept, side, kind) {
    const labels = SIDE_LABELS[kind];
    const body = labels ? sampleBody(concept[side]) : "";
    if (!body) return "";
    const why = concept[side].why ? `<p class="why">${cardText(concept[side].why)}</p>` : "";
    return `<span class="label-${side}">${label(...labels[side])}</span>${body}${why}`;
  }

  function optionCell([field, en, tr], option) {
    const text = cardText(option[field] || {});
    if (field === "name") return `<th scope="row">${text}</th>`;
    return `<td><span class="cell-label">${label(en, tr)}</span>${text}</td>`;
  }

  function tradeoffTable(concept) {
    const options = concept.options || [];
    if (!options.length) return "";
    const head = OPTION_COLUMNS.map(([, en, tr]) => `<th scope="col">${label(en, tr)}</th>`).join("");
    const rows = options.map((option) => `<tr>${OPTION_COLUMNS.map((c) => optionCell(c, option)).join("")}</tr>`);
    return `<table class="tradeoff"><thead><tr>${head}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
  }

  function structuredBody(concept) {
    const kind = kindOf(concept);
    const summary = concept.summary ? `<h4>${label("Concept", "Kavram")}</h4><p>${cardText(concept.summary)}</p>` : "";
    const middle = kind === "tradeoff" ? tradeoffTable(concept)
      : example(concept, "bad", kind) + example(concept, "good", kind);
    const tipLabel = TIP_LABELS[kind] || DEFAULT_TIP_LABEL;
    const tip = concept.tip ? `<div class="tip"><strong>${label(...tipLabel)}</strong>${cardText(concept.tip)}</div>` : "";
    return summary + middle + tip;
  }

  function open(concept) {
    document.getElementById("modal-title").innerHTML = Blocks.pair(concept.title);
    document.getElementById("modal-body").innerHTML = structuredBody(concept);
    document.getElementById("modal").classList.add("active");
    document.body.style.overflow = "hidden";
  }

  function close() {
    document.getElementById("modal").classList.remove("active");
    document.body.style.overflow = "";
  }

  function onChipClick(event) {
    const button = event.target.closest(".chip");
    if (!button) return;
    const concepts = byPage[button.dataset.page] || [];
    if (concepts[Number(button.dataset.concept)]) open(concepts[Number(button.dataset.concept)]);
  }

  function init() {
    document.getElementById("book").addEventListener("click", onChipClick);
    document.getElementById("modal-close").addEventListener("click", close);
    document.getElementById("modal").addEventListener("click", (event) => {
      if (event.target.id === "modal") close();
    });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
  }

  return { init, renderButtons, close };
})();
