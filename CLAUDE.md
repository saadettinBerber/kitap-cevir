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
- **Veri yapısı:** sayfa JSON'u (`references/FORMAT.md`) bir veri taşıyıcıdır. Davranışı `PageDocument` ve `Block` sarmalayıcıları taşır.

## Ölçüler: eşik alarmdır, ölçüt değildir

- **Fonksiyon (Bl.3):** idealde 2-4 satır, 20 satır tavandır. if/else bloğu tek satırlık bir çağrıdır, girinti 1-2 düzeyi geçmez. Tek iş, tek soyutlama düzeyi.
- **Argüman:** 0 > 1 > 2; 3'ten kaçınılır, fazlası olmaz. Bayrak argümanı ve çıktı argümanı yok. Komut ile sorgu ayrıdır (CQS).
- **Sınıf (Bl.10):** boyut sorumlulukla ölçülür. 200 satırı aşmak "büyük ihtimalle birden fazla iş" alarmıdır, ama altında kalmak doğruluk kanıtı değildir: tek bir değişme nedeni var mı?
- **Kurulum (Bl.11):** nesne bağımlılığını kendisi kurmaz, yapıcıdan alır. Bağlama işini `main` ya da `for_project` fabrikası yapar.
- **Kalıplar ihtiyaç doğunca gelir.** Tekrar eden tür dallanması → fabrika + polimorfizm. Üst düzey tekrar → TEMPLATE METHOD.

## Çalışma düzeni

- Testler: `python3 -m unittest discover -s tests`. Sınır koşulları test edilir (G3/T5); bir hata bulununca çevresi sıkı test edilir (T6).
- Davranışı koruyan yeniden düzenlemede testlerin yanında gerçek kitap çıktıları da eski kodla karşılaştırılır:
  - eski kodun `git worktree`'si
  - 30 sayfalık çıkarım (blok JSON + PNG özetleri)
  - finalize, regen, taşıma ve görsel ekleme akışları
- Yazdıktan sonra, commit'ten önce kod zihin haritasına göre bir daha ele alınır. Kalıp ihtiyacı çoğu zaman ancak yazılmış kodda görünür (Bl.3 · How Do You Write Functions Like This?, Bl.12 kural 2-4). Üç düzeyde bakılır:
  - fonksiyon (Bl.3): boyut, tek iş, argüman, CQS
  - sınıf (Bl.10, Bl.6): tek değişme nedeni, uyum, melez, elden ele taşınan değişken
  - sistem ve kalıp (Bl.11, Bl.12, haritanın "Bağlantılar" dalı): kurulum/kullanım ayrımı, tekrar, ihtiyaç → kalıp
  Bulgular haritadaki başlık adıyla yazılır; tereddütte kitaba bakılır. `clean-code-reviewer` ajanı kullanılmaz.
- Commit'ler atomiktir: tek değişiklik, tek cümlelik mesaj, gövde yok. Mesaja "ve" giriyorsa commit bölünür.
- Commit mesajları Türkçedir, yapay zeka imzası ya da `Co-Authored-By` satırı eklenmez. Commit yalnız istenince atılır.
