# {{TITLE}} — Çeviri Projesi

Bu proje, "{{TITLE}}" ({{AUTHOR}}) kitabını sayfa sayfa Türkçeye çevirip iki dilli,
kitap görünümlü interaktif okuyucuda sunar. Çeviri akışı global `kitap-cevir`
skill'i ile yürütülür: `/kitap-cevir N`, `/kitap-cevir next`, "sıradaki sayfa",
"devam et". Skill'in betikleri bu dizinde (progress.json'un yanında) çalıştırılır.

## Kurallar

- İlerlemenin tek doğruluk kaynağı `progress.json`'dur; betikler günceller, elle
  düzenlenmez. İstisna: kurulumda bir kez doldurulan `chapters` tablosu ve
  `extraction` ayarları.
- Kitap bilgileri (PDF adı, sayfa ofseti, bölümler, kod dili) `progress.json`'dadır;
  bu dosyada tekrarlanmaz.
- `glossary.md` terim sözlüğüdür: çeviriye başlamadan okunur, mevcut karşılıklar
  aynen kullanılır; yeni terimleri `finalize_page.py` ekler.
- `data/toc.js` ve `data/glossary.js` üretilen dosyalardır; elle düzenlenmez.
- Kod blokları, tanımlayıcılar, dosya yolları ve komutlar asla çevrilmez.
- Türkçe içerik doğru Türkçe karakterlerle yazılır (ç ğ ı ö ş ü, İ), UTF-8.
- Commit mesajı: `Sayfa N çevirisi eklendi — Chapter X: Title`; yapay zeka imzası
  veya `Co-Authored-By` satırı eklenmez.

## Okuyucu

- Açmak: `python3 -m http.server 8000` → http://localhost:8000
- CSS/JS değişince `index.html` içindeki `?v=N` sürüm ekini artır.
- Derin bağlantı: `index.html#page-N`.
