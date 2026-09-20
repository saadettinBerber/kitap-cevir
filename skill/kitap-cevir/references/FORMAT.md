# Sayfa Veri Formatı ve Çevirmen Agent Sözleşmesi

Her çevrilmiş sayfa `data/pages/page-N.js` dosyasında saklanır ve tek bir
`window.PAGE({...})` çağrısından oluşur. Okuyucu (`index.html` + `js/reader.js`)
bu nesneyi tipli bloklar halinde çizer.

```js
window.PAGE({
  "id": "page-5",
  "page": 5,                         // kitap sayfa numarası
  "pdf_page": 36,                    // PDF fiziksel sayfa (page + pdf_offset)
  "chapter": { "num": 1, "en": "Chapter Title", "tr": "Bölüm Başlığı" },
  "section": { "en": "Running Section Title", "tr": "Kesit Başlığı" },
  "title":   { "en": "Short page title", "tr": "Kısa sayfa başlığı" },
  "blocks":  [ ...aşağıdaki blok tipleri, sayfadaki sırayla... ],
  "concepts": [ ...kavram kartları... ]
});
```

- `section`: sayfanın üst kısmında geçerli olan kesit başlığı (kitaptaki koşu
  başlığı). Sayfa yeni bir başlıkla başlamıyorsa önceki sayfanın devamıdır.
- `title`: içindekiler ve sayfa kartlarında görünen kısa sayfa başlığı.

## İki dilli metin birimi

Her metin alanı `en` (orijinal) ve `tr` (çeviri) taşır. `html: true` ise her
iki alan da güvenli HTML içerebilir (yalnız `<code>`, `<strong>`, `<em>`,
`<br>`, `<sup>`); aksi halde düz metindir ve `` `kod` `` biçimindeki ters
tırnak parçaları okuyucuda `<code>` olarak çizilir.

## Blok tipleri

| type        | Alanlar                                                        | Açıklama |
|-------------|----------------------------------------------------------------|----------|
| `chapter`   | `num`, `en`, `tr`, `author?`                                   | Bölüm açılış başlığı (sadece bölümün ilk sayfasında) |
| `heading`   | `level` (1-3), `en`, `tr`                                      | Bölüm içi başlık. 1 = ana kesit, 2 = alt kesit, 3 = küçük etiket |
| `para`      | `sentences: [{en, tr, html?, words?}]`, `style?`               | Gövde paragrafı; cümle cümle. `style: "quote"` italik alıntı, `"reference"` kaynakça maddesi |
| `list`      | `ordered` (bool), `items: [{en, tr, html?}]`                   | Madde listesi |
| `code`      | `lang`, `code`, `caption?: {en, tr}`                           | Kod listesi. `code` ASLA çevrilmez; satır sonu ve girinti korunur |
| `caption`   | `en`, `tr`, `kind?`                                            | Şekil/listing/tablo açıklaması (`kind: "listing"` → listing başlığı olarak çizilir; `kind: "table"` → tablo başlığı) |
| `image`     | `src`                                                          | `data/pages/page-N_images/<src>` içindeki görsel |
| `footnote`  | `en`, `tr`                                                     | Sayfa altı dipnotu |
| `table`     | `rows: [[{en,tr,html?}]]`, `header_rows?`                      | Tablo; ilk `header_rows` satır `<th>` olarak çizilir. Hücre `html: true` ise `<sup>` (dipnot işareti) ve `<br>` (hücre içi liste) içerebilir; `tr` aynı etiketleri korur |
| `math`      | `src`, `text`, `latex`                                         | Ayrı satır denklemi. `src` = PNG (`page-N_images/eq-K.png`, her zaman var), `text` = düzleştirilmiş ham metin (yedek), `latex` = isteğe bağlı LaTeX. Çevrilmez |
| `html`      | `html`                                                         | Serbest HTML (nadiren; içinde `.tr-text` / `.en-text` span'ları olabilir) |

Kod bloklarında PDF'teki alt/üst simgeler `x^23`, `W_K` biçiminde düz metne
indirgenir; kod aynen korunur.

## Denklemler

- **Ayrı satır**: `math` bloğu. Okuyucu `latex` doluysa KaTeX ile çizer, boşsa
  ya da hatalıysa PNG'yi gösterir.
- **Satır içi**: cümle metninde `⟦eq-K⟧` yer tutucusu; karşılığı sayfa
  düzeyindeki `math` listesindedir: `"math": [{ "id": "eq-K", "src", "text",
  "latex" }]`. Yer tutucu `en` ve `tr` içinde **aynen** korunur (çevrilmez,
  taşınmaz). Tek sembol gibi basit satır içi denklemler yer tutucusuz, düz
  Unicode olarak metne girer (`θ`).
- **`latex` alanını kim doldurur?** Yalnız görsel okuyabilen bir çevirmen:
  PNG'yi açıp LaTeX yazar (`\log(\sigma(r_\theta(x, y_w) - r_\theta(x, y_l)))`).
  Çevirmen görsel okuyamıyorsa (yerel/metin-only model) `latex` boş bırakılır;
  boru hattı PNG ile eksiksiz çalışır. Bu ayar `progress.json → translator.vision`
  (varsayılan `true`) ile belirtilir ve `prepare_page.py` raporunda hatırlatılır.

`words` (isteğe bağlı): `[{w, t}]` — cümledeki kelimeler ve bağlama uygun
Türkçe anlamları. Varsa okuyucu kelimeye tıklayınca anlamını gösterir.

## Kavram kartları (`concepts`)

Her sayfa için 2-4 kart, yapılı biçimde:

```js
{
  "id": "kebab-case-id",
  "title":   { "en": "Concept Name", "tr": "Kavram Adı (Concept Name)" },
  "summary": { "en": "...", "tr": "..." },
  "bad":  { "lang": "java", "code": "...", "why": { "en": "...", "tr": "..." } },
  "good": { "lang": "java", "code": "...", "why": { "en": "...", "tr": "..." } },
  "tip":  { "en": "...", "tr": "..." }
}
```

Örnekler kitaptakinden FARKLI ve özgün olmalıdır (kitaptaki kod kopyalanmaz);
dil olarak Java / Python / JavaScript kullanılır. `body_html` alanı taşıyan
eski biçimli kartlar da olduğu gibi çizilir.

## Çevirmen agent girdisi ve çıktısı

`prepare_page.py`, `<proje>/_work/in/page-N.json` dosyasını üretir. Bu dosya
yukarıdaki şemanın yalnız `en` tarafını içerir; ayrıca bağlam için
`context.prev_tail` (önceki sayfanın sonu) ve `context.next_head`
(sonraki sayfanın başı) alanlarını taşır. Bağlam yalnız anlamak içindir,
çevrilmez. Agent:

1. `blocks` listesini **aynı sırada** korur, her `en` alanının yanına `tr` ekler
   (`code`, `image` ve `math` bloklarına dokunmaz; `math.latex` yalnız görsel
   okuyabiliyorsa doldurulur). Tablo hücrelerinde sayı/yüzde gibi çevrilmeyecek
   değerler için `tr` = `en`; `header_rows` aynen kalır. `⟦eq-K⟧` yer
   tutucuları `tr`'de aynen durur.
2. `section.tr`, `title.en`, `title.tr` alanlarını doldurur (`section.en`
   hazırlayıcı tarafından koşu başlığından tahmin edilir; yanlışsa düzeltir).
3. `chapter.tr` boşsa doldurur (bölüm tablosunda çeviri varsa onu kullanır).
4. `concepts` listesini (2-4 kart) yapılı biçimde üretir.
5. Sayfada geçen ve `glossary.md`'de olmayan yeni terimleri `glossary_new`
   listesine yazar: `[{ "en": "...", "tr": "...", "note": "..." }]`.
   Yeni terim yoksa boş liste bırakır.
6. Çıktıyı `<proje>/_work/out/page-N.json` olarak kaydeder (UTF-8, doğru Türkçe
   karakterler).

`finalize_page.py _work/out/page-N.json` bunu `data/pages/page-N.js`'e
işler, görselleri kopyalar, `progress.json`'u ilerletir, `data/toc.js` ve
`data/glossary.js` dosyalarını yeniden üretir ve `glossary_new` terimlerini
`glossary.md`'ye ekler. Boş `tr` alanı kalırsa uyarı verir.
