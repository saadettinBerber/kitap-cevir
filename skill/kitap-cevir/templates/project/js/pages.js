// Sayfa verisi yükleyici: data/pages/page-N.js dosyalarını <script> ile yükler, önbelleğe alır.
const Pages = (function () {
  const ASSET_VERSION = "1";
  const cache = {};
  const waiting = {};

  window.PAGE = function (page) {
    cache[page.page] = page;
    (waiting[page.page] || []).forEach((resolve) => resolve(page));
    delete waiting[page.page];
  };

  function startLoading(num, reject) {
    const script = document.createElement("script");
    script.src = `data/pages/page-${num}.js?v=${ASSET_VERSION}`;
    script.onerror = () => { delete waiting[num]; reject(new Error(`page-${num} yüklenemedi`)); };
    document.body.appendChild(script);
  }

  function load(num) {
    if (cache[num]) return Promise.resolve(cache[num]);
    return new Promise((resolve, reject) => {
      const isFirstRequest = !waiting[num];
      (waiting[num] = waiting[num] || []).push(resolve);
      if (isFirstRequest) startLoading(num, reject);
    });
  }

  return { load };
})();
