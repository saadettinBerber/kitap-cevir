# Çeviri Stil Kuralları

## Genel İlkeler

1. **Anlam odaklı çeviri yap, kelime kelime değil.** Cümlenin amacını ve öğretme
   niyetini koru.
2. **Türkçe doğallığını koru.** İngilizce cümle yapısını Türkçeye birebir taşıma.
3. **Teknik doğruluğu asla feda etme.** Sadeleştirirken teknik anlamı kaybetme.
4. **Kitabın pedagojik yapısını koru.** Başlıklar, alt başlıklar, numaralı listeler,
   madde işaretleri aynen korunur.
5. **ÖZET YASAKTIR.** Sayfadaki her cümle tam sadakatle çevrilir; `blocks` yapısı
   bunu zorunlu kılar (her `en` için bir `tr`).

## Parantezli Terminoloji (Parenthetical Terminology)

Teknik bir terim ilk kez geçtiğinde Türkçe karşılığı + (İngilizce orijinali):
"Tek Sorumluluk İlkesi (Single Responsibility Principle)". Aynı paragrafta tekrar
geçerse yalnız Türkçe karşılığı yeterlidir; farklı bir paragrafta yine parantezli
biçim kullanılır.

## Sözlük Tutarlılığı

Çeviriye başlamadan `glossary.md` okunur. Bir terim sözlükte varsa aynen o
karşılık kullanılır. Sözlükte olmayan her yeni terim çıktının `glossary_new`
listesine yazılır: `{ "en", "tr", "note" }`.

## Çevrilmeyecek Öğeler

- Kod blokları, kod parçaları, değişken/fonksiyon/sınıf adları
- Dosya adları ve yolları, komut satırı komutları
- Kütüphane ve framework adları (JUnit, Spring, React vb.)
- Yaygın kısaltmalar: API, HTTP, SQL, OOP, TDD, IDE, GUI, CLI
- Git terimleri: commit, push, pull, merge, branch
- Kitap, hareket ve ürün adları ("Clean Code", "Agile"; yanına Türkçe açıklama
  eklenebilir)
- Sektörde İngilizcesi yerleşmiş terimler (bug, debug, framework, library);
  gerekirse Türkçe açıklama eklenir

## Çevrilecek Öğeler

- Açıklama metinleri, anlatım paragrafları, kavramsal tanımlar
- Benzetmeler ve metaforlar (Türkçe karşılığı bulunarak; örn. "Boy Scout Rule"
  → "İzci Kuralı (Boy Scout Rule)")
- Alıntılar (alıntı olduğu belirtilerek)
- Başlıklar: hem Türkçe hem İngilizce tutulur (`en` / `tr` alanları)

## Üslup

- Yazarın samimi, deneyim paylaşan üslubunu yansıt.
- "Biz" ve "siz" zamirleriyle hitap et.
- Resmi değil ama profesyonel bir ton; kısa ve net cümleler.

## Türkçe Karakter Kuralı

Tüm Türkçe içerik doğru harflerle yazılır: ç ğ ı ö ş ü / Ç Ğ İ Ö Ş Ü. ASCII
karşılıkları (c, g, i, o, s, u) kabul edilmez. Dosyalar UTF-8'dir.
