# kitap-cevir: geliştirme yaklaşımı

Python kodu **OOP** ile ve *Clean Code* kitabının çerçevesiyle yazılır. Kaynak kitabın kendisidir.
Zihin haritası ve kitabı sorgulama yolu: `~/Desktop/clean code felsefesi/` (orada `CLAUDE.md`).

## Omurga: Kent Beck'in basit tasarımı (Bl.12, önem sırasıyla)

1. Tüm testler geçer. Test yazmak sınıfları tek sorumluluğa (**SRP**) ve dışarıdan verilen bağımlılığa (**DIP/DI**) iter.
2. Tekrar yok.
3. Niyet açık: iyi ad, küçük fonksiyon, standart kalıp adı.
4. En az sınıf ve metot. En düşük önceliktir: gereksiz sınıf açılmaz, dogmaya direnilir.

## İki yol ayrımı: nesne mi, veri yapısı mı? (Bl.6 · Data/Object Anti-Symmetry)

Kitap bunu `Geometry` (prosedürel) ile polimorfik `Shape` (OO) örneğiyle anlatır. Seçim, **hangi değişikliğin bekleneceğine** göre yapılır:

| Beklenen değişiklik | Seç | Neden |
|---|---|---|
| Yeni **tür** eklemek (yeni blok, yeni kart türü) | **OOP**: polimorfik sınıflar | Var olan fonksiyonlara dokunmadan yeni sınıf eklenir |
| Aynı veriye yeni **işlem** eklemek | **Prosedürel**: veri yapısı + fonksiyon | Var olan veri yapılarına dokunmadan yeni fonksiyon eklenir |

Tersi de doğrudur:
- Prosedürel kodda yeni tür eklemek bütün fonksiyonları değiştirir.
- OO kodda yeni işlem eklemek bütün sınıfları değiştirir.

"Her şey nesnedir" bir efsanedir. Yarı nesne yarı veri **melezlerden** kaçınılır.

Bu depodaki karşılıkları:
- **OOP:** `page_blocks.py`. Blok türü başına bir sınıf var, tür dallanması yalnız `Block.of` fabrikasında (G23 "tek switch"). Aynı dallanma daha önce beş modülde tekrar ediyordu.
- **OOP:** durum etrafında kurulan sınıflar (`CardChecker(spec)`, `PageInputBuilder`, `PdfInspector(document)`). Aynı değişken fonksiyondan fonksiyona elden ele taşınıyorsa orada bir sınıf çıkmak istiyordur (Bl.10 · Cohesion).
- **Prosedürel:** `extraction/text_utils.py`. Veri (metin) sabit, işlemler çoğalıyor, durum yok; sınıfa sarılmaz.
- **VISITOR:** `Block.accept` + `epub/block_visitor.py`. EPUB çıktısı bloklara eklenen yeni bir işlemdir; tür dallanması yine yalnız `Block.of`'ta kalır.
- **VISITOR:** `Card.of` (`concept_cards.py`) + `concept_check.CardRules` ve `epub/cards.EpubCardVisitor`. Kart türüne göre dallanma yalnız fabrikadadır; denetim ve EPUB çizimi karta eklenen işlemlerdir. Önceki sözlükle dağıtım (`kind_rules`, `_MIDDLE_PARTS`) aynı switch'in iki kopyasıydı.
- **POJO:** `epub/` diski bilmez. Stil, görsel ve çıktı akışı dışarıdan verilir; disk sınırı `export_epub.BookExport`'tur.
- **Veri yapısı:** sayfa JSON'u (`references/FORMAT.md`) bir veri taşıyıcıdır. Davranışı `PageDocument` ve `Block` sarmalayıcıları taşır.
- **Veri yapısı:** `progress.json` bir veri taşıyıcıdır. `Progress` onu sarar; kayıt yalnız kendi metotlarıyla değişir, `as_json()` yazılacak kopyayı verir (Bl.6 · Data/Object Anti-Symmetry).

## Ölçüler: eşik alarmdır, ölçüt değildir

- **Fonksiyon (Bl.3):** idealde 2-4 satır, 20 satır tavandır. if/else bloğu tek satırlık bir çağrıdır, girinti 1-2 düzeyi geçmez. Tek iş, tek soyutlama düzeyi.
- **Argüman:** 0 > 1 > 2; 3'ten kaçınılır, fazlası olmaz. Bayrak argümanı ve çıktı argümanı yok. Komut ile sorgu ayrıdır (CQS).
- **Sınıf (Bl.10):** boyut sorumlulukla ölçülür. 200 satırı aşmak "büyük ihtimalle birden fazla iş" alarmıdır, ama altında kalmak doğruluk kanıtı değildir: tek bir değişme nedeni var mı?
- **Kurulum (Bl.11):** nesne bağımlılığını kendisi kurmaz, yapıcıdan alır. Bağlama işini `main` ya da `for_project` fabrikası yapar.
- **Kalıplar ihtiyaç doğunca gelir.** Tekrar eden tür dallanması → fabrika + polimorfizm. Üst düzey tekrar → TEMPLATE METHOD.

## Çalışma düzeni

- Testler: `python3 -m unittest discover -s tests`. Sınır koşulları test edilir (G3/T5); bir hata bulununca çevresi sıkı test edilir (T6).
- Testler F.I.R.S.T'tir (Bl.9):
  - **Fast:** milisaniyede koşar.
  - **Independent:** birbirine ve sıraya bağlı değildir.
  - **Repeatable:** PDF'e, Java'ya, masaüstündeki kitaplara bağlı değildir; sahteler `tests/pdf_fakes.py`'dedir.
  - **Self-Validating:** geçti ya da kaldı der, çıktıya bakmak gerekmez.
  - **Timely:** kodla birlikte yazılır; testi olmayan kural yeniden düzenlenmeden önce testle sabitlenir.

  Test başına tek kavram; eşiğin iki yanı ayrı testtir. Gerçek PDF açan testler yalnız kütüphanenin öğrenme testleridir (Bl.8).
- Davranışı koruyan yeniden düzenlemede testlerin yanında gerçek kitap çıktıları da eski kodla karşılaştırılır:
  - eski kodun `git worktree`'si
  - 30 sayfalık çıkarım (blok JSON + PNG özetleri)
  - finalize, regen, taşıma ve görsel ekleme akışları

  Bu karşılaştırma test değildir; yeniden düzenleme sırasında elle koşulan iskeledir ve test takımına girmez. Fark bulursa önce o farkı gösteren birim testi yazılır, sonra kod düzeltilir (T6).
- Yazdıktan sonra, commit'ten önce kod bir daha ele alınır. Kimse ilk seferde istediği gibi yazamaz; kalıp ihtiyacı çoğu zaman ancak yazılmış kodda görünür (Bl.3 · How Do You Write Functions Like This?, Bl.12 kural 2-4). Önce `olc.py` ile ölçülür, sonra tamam tanımına göre okunur. Bulgular haritadaki başlık adıyla yazılır; tereddütte kitaba bakılır. `clean-code-reviewer` ajanı kullanılmaz.
- Commit'ler atomiktir: tek değişiklik, tek cümlelik mesaj, gövde yok. Mesaja "ve" giriyorsa commit bölünür.
- Commit mesajları Türkçedir, yapay zeka imzası ya da `Co-Authored-By` satırı eklenmez.

## Tamam tanımı

Kitap bir standarttır: kural dile ya da alışkanlığa göre gevşetilmez. Bir görevin ne zaman bittiğini `~/Desktop/clean code felsefesi/tamam-tanimi.md` söyler. Liste kitabın her bölümünü başlık adıyla kapsar; kalıpların hangi ihtiyaçla geleceği de oradadır.

1. Bütün testler geçer.
2. `python3 ~/Desktop/"clean code felsefesi"/olc.py <değişen dosyalar>` çalışır. Her ALARM "gerçek, düzeltildi" ya da "yanlış pozitif, çünkü…" diye karara bağlanır. Eşik alarmdır; asıl ölçü sorumluluk ve niyettir.
3. Listenin okuma maddeleri üç düzeyde işaretlenir: fonksiyon, sınıf, sistem ve kalıp.
4. Davranış değiştiyse gerçek kitap çıktısı üretilip görülür. Yeniden düzenlemeyse eski kodla karşılaştırılır.

Hepsi sağlanınca atomik commit atılır ve bu depo push edilir; ayrıca sorulmaz. Kullanıcıya her maddenin kanıtıyla kısa bir rapor verilir.

Bir madde sağlanamıyorsa, bir alarm için karar verilemiyorsa ya da kullanıcının vermesi gereken bir tasarım kararı çıktıysa commit atılmaz, sorulur. Kitap depolarında alt modül güncellemesi ve push ayrıca istenir.
