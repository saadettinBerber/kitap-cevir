---
name: kitap-cevir
description: İngilizce bir PDF kitabı sayfa sayfa Türkçeye çevirip iki dilli, kitap görünümlü interaktif okuyucuya ekler. "init" ile yeni kitap projesi (okuyucu iskeleti + progress.json + sözlük) kurar; sayfa numarası veya "next / sıradaki sayfa" ile çeviri yapar; "cards" ile çevrilmiş sayfaların kavram kartlarını yeniden üretir. Tetikleyiciler - /kitap-cevir, "kitap çevir", "PDF kitabı çevir", "yeni kitap projesi", "sıradaki sayfa", "devam et", "okuyucu iskeleti", "kartları yenile".
argument-hint: "[init | N | next | next --count K | cards N-M|all | backfill]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Agent"]
---

# Kitap Çeviri Skill'i (PDF → iki dilli okuyucu)

Skill dizini: `~/.claude/skills/kitap-cevir` (aşağıda `$SKILL`). Betikler
`$SKILL/scripts/` altındadır ve **her zaman kitap projesinin dizininde**
(içinde `progress.json` olan dizin) çalıştırılır; betikler kökü kendileri
bulur (`KITAP_ROOT` ortam değişkeni ile de gösterilebilir). Dil çifti bu
sürümde sabittir: kaynak İngilizce (`en`), hedef Türkçe (`tr`).

```bash
SKILL=~/.claude/skills/kitap-cevir
```

## Hangi mod?

| `$ARGUMENTS` / istek | Mod |
|----------------------|-----|
| `init`, "yeni kitap projesi", "bu PDF'i kur" | **A. Kurulum** |
| sayı (`55`), `next`, boş, "sıradaki sayfa", "devam et", `next --count 3` | **B. Sayfa çevirisi** |
| `cards 5-40`, `cards all`, "kartları yenile" | **C. Kart yenileme** |
| `backfill` | Çevrilmiş sayfalara PDF görsellerini geriye dönük ekle: `python3 $SKILL/scripts/backfill_images.py [N ...]` |

## Bağımlılıklar

`python3`, `pip install -U opendataloader-pdf pymupdf`, Java 11+ (OpenDataLoader
Java tabanlıdır). `ModuleNotFoundError` görürsen pip komutunu çalıştır; `java`
yoksa kullanıcıdan kurmasını iste (`sudo apt install default-jre` vb.).

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
   `data/glossary.js` yeniden üretilir. `UYARI: ... 'tr' alanı boş` ya da
   `! KART: ...` satırları çıkarsa çıktı JSON'unu düzelt ve yeniden çalıştır.
5. **Doğrula ve raporla**: `data/pages/page-N.js`'yi kısaca kontrol et
   (Türkçe karakterler, kod bloğu bozulmamış). Kullanıcıya hangi sayfaların
   çevrildiğini ve sıradaki sayfa numarasını bildir.
6. **Commit ve push**: projenin `CLAUDE.md` kuralına göre. Varsayılan mesaj:
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
Kavram kartları: 2-4 kart, FORMAT.md "Kavram kartları" bölümüne göre. Önce
sayfanın öğrettiği kavramları seç, sonra her biri için `concepts_spec.kinds`
içinden konuya uyan türü seç; kalıba uysun diye konuyu değiştirme, sayfada
anlatılmayan bir kod örneği uydurma. Sözlükte olmayan terimleri
`glossary_new`'e yaz. `context` alanı yalnız bağlam içindir, çevrilmez. Özet
yasaktır; her cümle tam çevrilir. Parantezli terminoloji, iki dilli başlıklar,
doğru Türkçe karakterler.
Çıktıyı <proje>/_work/out/page-N.json olarak UTF-8 kaydet; başka bir şey yazma.
```

## C. Kart yenileme (`cards`)

Çevrilmiş sayfaların metnine dokunmadan yalnız `concepts` listesini yeniden
ürettirir (kart türleri değiştiğinde ya da kartlar sayfayla ilgisiz çıktığında).

1. Gerekirse önce `progress.json → concepts.kinds` listesini kitaba göre ayarla
   (A.4'teki tablo). Okuyucu dosyaları eskiyse (`js/concepts.js`,
   `js/highlight.js`, `css/reader.css`) `$SKILL/templates/project/`'ten kopyala
   ve `index.html`'deki `?v=N` eklerini artır; yoksa yeni kart türleri çizilmez.
2. **Hazırla**: `python3 $SKILL/scripts/regen_concepts.py prepare 5-40`
   (`all`, tek tek numaralar ya da aralıklar) → `_work/cards/in/page-N.json`:
   sayfanın iki dilli metni (`content`), başlıklar ve `concepts_spec`.
3. **Kart agent'ları**: sayfa başına bir `general-purpose` agent, tek mesajda
   paralel (bir seferde en çok ~10). Şablon (yolları mutlak yaz):
   ```
   Şu dosyaları oku: $SKILL/references/FORMAT.md ("Kavram kartları" bölümü),
   <proje>/glossary.md, <proje>/_work/cards/in/page-N.json.
   Görev: sayfanın `content` metninden 2-4 kavram kartı üret. Önce sayfanın
   öğrettiği kavramları seç, sonra her biri için `concepts_spec.kinds` içinden
   konuya uyan türü seç. Konuyu kalıba uydurma; sayfada anlatılmayan kod
   örneği uydurma. Türkçe terimler sayfanın `tr` metni ve sözlükle tutarlı olsun.
   Çıktı: <proje>/_work/cards/out/page-N.json = {"concepts": [...]} (UTF-8);
   başka bir şey yazma.
   ```
4. **Uygula**: `python3 $SKILL/scripts/regen_concepts.py apply 5-40`. Kartlar
   denetlenir; geçerliyse `data/pages/page-N.js`'e yazılır. Sorunlu sayfalar
   yazılmaz, sorunlar basılır: o sayfaların çıktısını düzelt (ya da agent'ı
   yeniden çalıştır) ve yalnız onlar için `apply`'ı tekrarla.
5. Raporla (yazılan / sorunlu sayfa sayısı) ve projenin `CLAUDE.md` kuralına
   göre commit: `Sayfa A-B kavram kartları yenilendi`.

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
| Tablo düz metin olarak geliyor | Dolgulu (zebra) tablolar `table_scan.py` ile otomatik yakalanır; çizgisiz-dolgusuz tablolar için `references/extraction.md` belirti tablosu |
| Okuyucu eski veriyi gösteriyor | `index.html`'deki `?v=N` sürüm ekini artır |
| Kavram kartları sayfanın konusuyla ilgisiz kod örneğine dönüşüyor | `progress.json → concepts.kinds` listesini kitaba göre daralt (A.4 tablosu), sonra **C. Kart yenileme** |
| `! KART: tür 'code' bu kitapta izinli değil` | Agent izinsiz tür seçmiş; çıktıyı düzelt ya da `concepts.kinds`'ı gözden geçir |

## Ayrıntılı referanslar (gerektiğinde oku)

- `references/FORMAT.md` — sayfa veri formatı, blok tipleri, agent sözleşmesi
- `references/translation-style.md` — çeviri kuralları ve üslup
- `references/extraction.md` — çıkarım ayarları, ölçme ve belirti/çözüm tablosu
- `templates/project/` — `init` ile kopyalanan okuyucu iskeleti
