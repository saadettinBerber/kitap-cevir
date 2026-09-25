---
name: kitap-cevir
description: İngilizce bir PDF kitabı sayfa sayfa Türkçeye çevirip iki dilli, kitap görünümlü interaktif okuyucuya ekler. "init" ile yeni kitap projesi (okuyucu iskeleti + progress.json + sözlük) kurar; sayfa numarası veya "next / sıradaki sayfa" ile çeviri yapar, kavram kartlarını çeviriden sonra ayrı üretir; "cards" ile çevrilmiş sayfaların kartlarını yeniden üretir; "migrate" ile çevrilmiş sayfaları yeni çıkarıma taşır. Tetikleyiciler - /kitap-cevir, "kitap çevir", "PDF kitabı çevir", "yeni kitap projesi", "sıradaki sayfa", "devam et", "okuyucu iskeleti", "kartları yenile".
argument-hint: "[init | N | next | next --count K | cards N-M|all | migrate N|all | backfill]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Agent"]
---

# Kitap Çeviri Skill'i (PDF → iki dilli okuyucu)

Skill dizini: `${CLAUDE_SKILL_DIR}` (aşağıda `$SKILL`). Betikler
`$SKILL/scripts/` altındadır ve **her zaman kitap projesinin dizininde**
(içinde `progress.json` olan dizin) çalıştırılır; betikler kökü kendileri
bulur (`KITAP_ROOT` ortam değişkeni ile de gösterilebilir). Dil çifti bu
sürümde sabittir: kaynak İngilizce (`en`), hedef Türkçe (`tr`).

```bash
SKILL="${CLAUDE_SKILL_DIR}"
```

`references/` dosyalarındaki `$SKILL` de bu dizindir.

## Hangi mod?

| `$ARGUMENTS` / istek | Mod |
|----------------------|-----|
| `init`, "yeni kitap projesi", "bu PDF'i kur" | **A. Kurulum** |
| sayı (`55`), `next`, boş, "sıradaki sayfa", "devam et", `next --count 3` | **B. Sayfa çevirisi** |
| `cards 5-40`, `cards all`, "kartları yenile" | **C. Kavram kartları** |
| `migrate 5 13`, `migrate all`, "sayfaları yeni çıkarıma taşı" | **D. Taşıma** |
| `backfill` | Çevrilmiş sayfalara PDF görsellerini geriye dönük ekle: `python3 $SKILL/scripts/backfill_images.py [N ...]` |
| `epub`, "Kindle", "Kindle'da oku" | **E. Kindle (EPUB)** |

## Görevler ve kimin yürüttüğü

İş üç ayrı **görev tanımına** bölünür; her birinin kendi girdisi, çıktısı ve
şablonu vardır. Bölünen görevdir, yürütücü değil:

| Görev | Girdi → çıktı | Şablon |
|-------|---------------|--------|
| Çıkarım (betik) | PDF sayfası → `_work/in/page-N.json` (yalnız `en`) | `prepare_page.py` |
| Çeviri | `_work/in/page-N.json` → `_work/out/page-N.json` (`tr`, kart yok) | B → Çevirmen agent şablonu |
| Kartlar (en son) | `_work/cards/in/page-N.json` → `_work/cards/out/page-N.json` | C.3 şablonu |

Alt agent açılabiliyorsa çeviri ve kart görevleri paralel alt agent'lara
verilir. Açılamıyorsa (araç yok, izin yok ya da tek agent'lı bir ortam) **aynı
şablonları ana agent sırayla kendisi uygular**: önce sayfaları çevirip
sonlandırır, sonra kartlara geçer. Çeviri sırasında kart üretilmez; görevler
aynı agent'ta da birbirine karışmaz.

## Bağımlılıklar

`python3`, `pip install -U opendataloader-pdf pymupdf`, Java 11+ (OpenDataLoader
Java tabanlıdır). `ModuleNotFoundError` görürsen pip komutunu çalıştır; `java`
yoksa kullanıcıdan kurmasını iste (`sudo apt install default-jre` vb.).
`progress.json -> extraction.layout_reader: "liteparse"` seçilen kitapta ayrıca
`pip install -U liteparse` gerekir (Java gerekmez).

## A. Kurulum (`init`)

Amaç: `progress.json` + `glossary.md` + `CLAUDE.md` + okuyucu iskeleti olan bir
kitap projesi. Kullanıcıdan PDF yolu ve hedef dizin eksikse sor; gerisini
sen çıkar.

1. **PDF'i tanı**
   ```bash
   python3 $SKILL/scripts/inspect_pdf.py <pdf> info
   python3 $SKILL/scripts/inspect_pdf.py <pdf> offset
   ```
   `offset`, basılı sayfa numaralarından "PDF sayfası − kitap sayfası" değerini
   oylar. En çok oy alan adayı `text` ile doğrula: PDF sayfa P'nin metninde
   basılı numara `P − offset` olmalı (bölüm açılışlarında folyo olmayabilir,
   normal bir gövde sayfası seç).
2. **Bölüm tablosu**: içindekiler sayfalarını oku
   (`inspect_pdf.py <pdf> text 5-9` gibi), her bölüm için
   `{"num", "en", "tr", "start"}` yaz (`start` = **kitap** sayfası, PDF değil;
   `tr` = başlığın Türkçesi). Önsöz/giriş gibi numarasız kısımlar için `num`
   0 verilebilir. Bu listeyi geçici bir `chapters.json` dosyasına kaydet.
3. **Toplam sayfa**: kitabın son basılı sayfa numarası (`--total`). Dizin ve
   ekler dahil edilecekse onları da say.
4. **Kur**:
   ```bash
   python3 $SKILL/scripts/init_book.py --pdf <pdf> --title "..." --author "..." \
     --offset <N> --total <M> --chapters chapters.json --target <dizin> \
     [--subtitle "..."] [--subtitle-tr "..."] [--series "..."] [--code-lang python] \
     [--card-kinds explain,contrast,tradeoff,code]
   ```
   PDF projeye `book.pdf` olarak kopyalanır ve `.gitignore` ile dışarıda tutulur.
   **Kart türlerini kitaba göre seç** (kullanıcıya önerini söyle, emin değilse sor);
   çevirmen her kart için bu listeden konuya uyanı seçer
   (`references/FORMAT.md` → Kavram kartları):

   | Kitap türü | `--card-kinds` |
   |------------|----------------|
   | Kod zanaatı (Clean Code, Refactoring, Effective Java) | `code,contrast,explain` |
   | Mimari, sistem tasarımı, süreç | `tradeoff,contrast,explain` |
   | Kavramsal / uygulamalı teknik (AI/ML, veri, ağ) | varsayılan (dördü de) |
   | Anlatı, iş, yönetim | `explain,contrast` |
5. **Çıkarım ayarlarını akort et**: kod içeren bir PDF sayfası ile bir bölüm
   açılış sayfası için
   `python3 $SKILL/scripts/inspect_pdf.py <pdf> layout <P>` çalıştır; kod fontu,
   koşu başlığı yüksekliği ve başlık boyutlarını `references/extraction.md`'deki
   varsayılanlarla karşılaştır. Farklıysa `progress.json` → `extraction` içine
   yalnız değişen anahtarları yaz (kurulumda tek seferlik elle düzenleme
   serbesttir). Sonra `python3 $SKILL/scripts/prepare_page.py 1` ile deneme
   çıkarımı yap ve `_work/in/page-1.json`'daki blok tiplerini gözle kontrol et.
6. Çevirmen olarak görsel okuyamayan bir model kullanılacaksa `progress.json`
   → `translator.vision` değerini `false` yap (denklem PNG'lerinden LaTeX
   istenmez).
7. Kullanıcı isterse `git init` + ilk commit. Raporla: proje yolu, ofset,
   bölüm sayısı, okuyucu komutu (`python3 -m http.server 8000`).

## B. Sayfa çevirisi

1. **Sözlüğü oku**: projedeki `glossary.md`; mevcut terimler aynen kullanılır.
2. **Hazırla**
   ```bash
   python3 $SKILL/scripts/prepare_page.py            # sıradaki pages_per_run sayfa
   python3 $SKILL/scripts/prepare_page.py 55         # yalnız sayfa 55
   python3 $SKILL/scripts/prepare_page.py next --count 3
   ```
   Çıktı: `_work/in/page-N.json` (blok şemasının `en` tarafı, `context.prev_tail`
   / `context.next_head`, hazır `chapter`, tahmini `section.en`). Boş sayfalar
   "next" akışında atlanıp `blank` işaretlenir.
3. **Çevir — paralel çevirmen agent'lar**: hazırlanan HER sayfa için bir
   `general-purpose` agent, hepsi TEK mesajda paralel. Her agent'a aşağıdaki
   şablonu ver. Agent `_work/out/page-N.json` yazar. Sayfada denklem varsa
   (`prepare_page` raporunda "denklem: K PNG") şablondaki köşeli parantezli
   satırlardan `progress.json → translator.vision` değerine uyanı ekle:
   görsel okuyamayan bir çevirmen (yerel/metin-only model) `latex` üretemez,
   PNG yeter.
4. **Sonlandır** (sayfa sayfa, sırayla):
   ```bash
   python3 $SKILL/scripts/finalize_page.py _work/out/page-N.json
   ```
   `data/pages/page-N.js` yazılır, görseller kopyalanır, `progress.json`
   ilerler, `glossary_new` terimleri `glossary.md`'ye eklenir, `data/toc.js` ve
   `data/glossary.js` yeniden üretilir. `UYARI: ... 'tr' alanı boş` satırı
   çıkarsa çıktı JSON'unu düzelt ve yeniden çalıştır. `kartlar bekliyor`
   satırı normaldir: kartlar bir sonraki adımda üretilir.
5. **Kartlar en son**: çevrilen sayfalar sonlandırıldıktan sonra, aynı sayfalar
   için **C.2-C.4** adımlarını çalıştır. Kart agent'ı kesinleşmiş Türkçe metni
   ve güncel sözlüğü görür; ardışık sayfalar tek agent'ta toplandığı için
   komşu sayfalarda aynı kavram tekrar kart olmaz.
6. **Doğrula ve raporla**: `data/pages/page-N.js`'yi kısaca kontrol et
   (Türkçe karakterler, kod bloğu bozulmamış, kartlar çiziliyor). Kullanıcıya
   hangi sayfaların çevrildiğini ve sıradaki sayfa numarasını bildir.
7. **Commit ve push**: projenin `CLAUDE.md` kuralına göre. Varsayılan mesaj:
   `Sayfa N çevirisi eklendi — Chapter X: Title`; yapay zeka imzası yok.

### Çevirmen agent şablonu

Agent'a vermeden önce `$SKILL` ve `<proje>` yerine **mutlak yolları** yaz
(`Read` aracı `~` ve kabuk değişkenlerini açmaz); `N` yerine sayfa numarasını.

```
Sen bir teknik kitap çevirmenisin. Şu dosyaları oku:
- $SKILL/references/FORMAT.md   (veri formatı, kavram kartları, çıktı sözleşmesi)
- $SKILL/references/translation-style.md   (çeviri kuralları)
- <proje>/glossary.md   (terim sözlüğü; mevcut karşılıklar aynen kullanılır)
- <proje>/_work/in/page-N.json   (girdi)

Görev: girdideki her `en` alanının yanına `tr` ekle (heading, para cümleleri,
list maddeleri, caption, footnote, table hücreleri, chapter). Blok sırası ve
sayısı aynen korunur. `code`, `image` ve `math` bloklarına DOKUNMA; cümledeki
`⟦eq-K⟧` yer tutucuları `tr`'de aynen kalır. Tablo hücrelerinde sayı/yüzde
için `tr` = `en`; `header_rows` ve `html: true` hücrelerdeki `<sup>`/`<br>`
etiketleri `tr`'de de aynen kalır.
[translator.vision=true ise ekle:] Görsel okuyabiliyorsun: `math` bloklarının
ve sayfa düzeyindeki `math` listesinin PNG'lerini (<proje>/_work/in/page-N_images/)
aç, her birinin `latex` alanına KaTeX ile çizilebilir LaTeX yaz ($ işareti yok).
[translator.vision=false ise ekle:] `latex` alanlarını boş bırak; okuyucu PNG kullanır.
`section.tr`, `title.en`, `title.tr`, boşsa `chapter.tr` doldur.
`concepts` listesini boş bırak: kavram kartları çeviriden sonra ayrı üretilir.
Sözlükte olmayan terimleri
`glossary_new`'e yaz. `context` alanı yalnız bağlam içindir, çevrilmez. Özet
yasaktır; her cümle tam çevrilir. Parantezli terminoloji, iki dilli başlıklar,
doğru Türkçe karakterler.
Çıktıyı <proje>/_work/out/page-N.json olarak UTF-8 kaydet; başka bir şey yazma.
```

## C. Kavram kartları (`cards`)

Kartlar çeviriden ayrı ve en son üretilir; sayfa metnine dokunulmaz. Bu akış
hem yeni çevrilen sayfalar için (B.5) hem de kart türleri değiştiğinde ya da
kartlar sayfayla ilgisiz çıktığında tüm sayfaları yenilemek için kullanılır.

1. Gerekirse önce `progress.json → concepts.kinds` listesini kitaba göre ayarla
   (A.4'teki tablo). Okuyucu dosyaları eskiyse (`js/concepts.js`,
   `js/highlight.js`, `css/reader.css`) `$SKILL/templates/project/`'ten kopyala
   ve `index.html`'deki `?v=N` eklerini artır; yoksa yeni kart türleri çizilmez.
2. **Hazırla**: `python3 $SKILL/scripts/regen_concepts.py prepare 5-40`
   (`all`, tek tek numaralar ya da aralıklar) → `_work/cards/in/page-N.json`:
   sayfanın iki dilli metni (`content`), başlıklar ve `concepts_spec`.
3. **Kart agent'ları**: ardışık en çok 5 sayfa bir agent'a (aynı bölümün
   sayfaları bir arada; bölüm sınırında grup kesilir). `general-purpose`
   agent'lar tek mesajda paralel, bir seferde en çok ~10. Şablon (yolları
   mutlak yaz, `A..B` yerine gruptaki sayfaları):
   ```
   Şu dosyaları oku: $SKILL/references/FORMAT.md ("Kavram kartları" bölümü),
   <proje>/glossary.md ve <proje>/_work/cards/in/page-A.json .. page-B.json
   (ardışık sayfalar; birbirlerinin bağlamıdır).
   Görev: HER sayfa için o sayfanın `content` metninden 2-4 kavram kartı üret.
   Önce sayfanın öğrettiği kavramları seç, sonra her biri için
   `concepts_spec.kinds` içinden konuya uyan türü seç. Konuyu kalıba uydurma;
   sayfada anlatılmayan kod örneği uydurma. Bir kavram birden çok sayfada
   geçiyorsa kartı onu asıl anlatan sayfaya koy, komşu sayfada tekrarlama.
   Türkçe terimler sayfanın `tr` metni ve sözlükle tutarlı olsun.
   Çıktı: her sayfa için <proje>/_work/cards/out/page-N.json =
   {"concepts": [...]} (UTF-8); başka bir şey yazma.
   ```
4. **Uygula**: `python3 $SKILL/scripts/regen_concepts.py apply 5-40`. Kartlar
   denetlenir; geçerliyse `data/pages/page-N.js`'e yazılır. Sorunlu sayfalar
   yazılmaz, sorunlar basılır: o sayfaların çıktısını düzelt (ya da agent'ı
   yeniden çalıştır) ve yalnız onlar için `apply`'ı tekrarla.
5. Raporla (yazılan / sorunlu sayfa sayısı) ve projenin `CLAUDE.md` kuralına
   göre commit: yeni çeviride B.7'deki mesaj, yenilemede
   `Sayfa A-B kavram kartları yenilendi`.

## D. Taşıma (`migrate`)

Çıkarım iyileştiğinde (skill güncellemesi) ya da `extraction` ayarları
değiştiğinde çevrilmiş sayfaları **yeniden çevirmeden** yeni blok yapısına
taşır: sayfa yeniden çıkarılır, eski `en→tr` eşleşmeleri (birebir, normalize,
bölünmüş/birleşmiş cümle) yeni birimlere işlenir; başlık, kesit, kartlar ve
denklem LaTeX'i aynen kalır.

1. **Taşı**: `python3 $SKILL/scripts/migrate_page.py 5 13 121` (ya da `all`).
   Eşleşmesi tam olan sayfa hemen sonlandırılır (`--no-finalize` ile ertelenir).
   Eşleşmeyen birimler `_work/migrate/pending-N.json`'a düşer:
   `units: [{path, en, tr_hint}]`, `latex: [{path, src}]`.
2. **Bekleyenleri çevir** (varsa): sayfa başına bir `general-purpose` agent;
   `pending-N.json`'ı, `glossary.md`'yi ve `references/translation-style.md`'yi
   okur, her birimi çevirir (`tr_hint` eski çeviridir, uyuyorsa kullanılır),
   `latex` öğeleri için PNG'yi (`_work/in/page-N_images/<src>`) açıp LaTeX yazar
   (`translator.vision=false` ise `latex` boş kalır). Çıktı:
   `_work/migrate/done-N.json` = `{"units": [{path, tr}], "latex": [{path, latex}]}`;
   `path` değerleri aynen korunur.
3. **Uygula**: `python3 $SKILL/scripts/migrate_page.py apply 5 13` → çeviriler
   yerine yazılır, sayfa sonlandırılır.
4. Birkaç taşınan sayfayı okuyucuda kontrol et, commit: `Sayfa A-B yeni çıkarıma taşındı`.

## E. Kindle (`epub`)

Çevrilmiş sayfalardan Kindle için akışkan bir EPUB 3 üretir; okuyucuya
dokunmaz, aynı sayfa verisini okur.

```bash
python3 $SKILL/scripts/export_epub.py      # → dist/<slug>.epub
```

- Bölüm başına bir dosya; PDF sayfa sınırında bölünen paragraf birleşir,
  basılı sayfa numarası Kindle'ın sayfa listesinde durur.
- Metin Türkçe akar; paragraf, madde, altyazı ve dipnot sonundaki **EN**
  bağlantısı İngilizce aslını açılır pencerede gösterir.
- Denklemler PNG'dir (KaTeX yok); kavram kartları bölüm sonunda,
  "Kavram kartları" kesitindedir; tablo hücreleri yalnız Türkçedir.
- Kullanıcıya dosyayı Send to Kindle ile (e-posta, web ya da uygulama)
  göndermesini söyle; kitap kimliği slug'dan türediği için yeni sürüm aynı kitabın
  yerine geçer. Gönderimi agent yapmaz.
- `dist/` git'e girmez (`.gitignore`).

## Sorun giderme

| Belirti | Yapılacak |
|---------|-----------|
| `progress.json bulunamadı` | Proje dizininde çalıştır ya da `KITAP_ROOT=<dizin>` ver |
| `ModuleNotFoundError` | `python3 -m pip install -U opendataloader-pdf pymupdf` |
| "Sayfa N boş" ama değil | `pdf_offset` yanlış → `inspect_pdf.py offset` |
| Kod paragraf olarak geliyor, başlıklar yanlış | `references/extraction.md` → `layout` ile ölç, `extraction` ayarla |
| Denklem kayboluyor / `latex` boş | Denklem fontu Type3 değilse `references/extraction.md` → `math_font_prefix`; çevirmen görsel okuyamıyorsa `translator.vision` = `false` (PNG her zaman gösterilir) |
| Tablonun bütün satırları tek hücrede `<br>` ile birleşik | `table_row_gap_ratio` kitaba göre ölçülmeli (`references/extraction.md`) |
| Sayfadan koca bir bölüm (tablo, başlık, paragraf) eksik | ODL caption'ı liste sanıp altına gömmüş olabilir; `flatten_nested_lists` bunu açar, açmıyorsa ham ODL çıktısına bak |
| Tablo düz metin olarak geliyor | Dolgulu (zebra), kenarlık çizgili ve kalın başlıklı sütun hizalı tablolar (sayfaya bölünmüşleri dahil) otomatik yakalanır. Geri kalanı elle `table` bloğuna çevrilir (`references/extraction.md` belirti tablosu) |
| Sayfanın ilk paragrafı çıkarımda yok | Kitapta koşu başlığı yok: `extraction.running_header` = `"none"` |
| Kod listelerinin üstünde "Click here to view code image" | E-kitap bağlantısı: `extraction.code_image_link_pattern` = `"Click here to view code image"` |
| Çıkarım düzeldi ama eski sayfalar eski yapıda | **D. Taşıma** (yeniden çeviri gerekmez) |
| Okuyucu eski veriyi gösteriyor | `index.html`'deki `?v=N` sürüm ekini artır |
| Kavram kartları sayfanın konusuyla ilgisiz kod örneğine dönüşüyor | `progress.json → concepts.kinds` listesini kitaba göre daralt (A.4 tablosu), sonra **C. Kavram kartları** |
| `MalformedXhtml: text/chapter-NN.xhtml` | Bir sayfanın HTML birimi bozuk; hata satırındaki sayfayı düzelt, EPUB'ı yeniden üret |
| `! KART: tür 'code' bu kitapta izinli değil` | Agent izinsiz tür seçmiş; çıktıyı düzelt ya da `concepts.kinds`'ı gözden geçir |

## Ayrıntılı referanslar (gerektiğinde oku)

- `references/FORMAT.md` — sayfa veri formatı, blok tipleri, agent sözleşmesi
- `references/translation-style.md` — çeviri kuralları ve üslup
- `references/extraction.md` — çıkarım ayarları, ölçme ve belirti/çözüm tablosu
- `templates/project/` — `init` ile kopyalanan okuyucu iskeleti
