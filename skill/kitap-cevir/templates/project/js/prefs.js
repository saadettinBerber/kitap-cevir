// Tarayıcı tercihleri için kitaba özel localStorage anahtarları (window.TOC.book.slug).
// Aynı sunucuda birden fazla kitap okuyucusu varsa tercihler birbirine karışmaz.
const Prefs = (function () {
  const FALLBACK_SLUG = "kitap";

  function slug() {
    return (window.TOC && window.TOC.book && window.TOC.book.slug) || FALLBACK_SLUG;
  }

  function key(name) { return `${slug()}-${name}`; }

  return { key };
})();
