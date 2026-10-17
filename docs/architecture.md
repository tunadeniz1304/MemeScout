# MemeScout — Mimari Tasarım

> Durum: Taslak. Etiket listeleri ve açık sorular netleştikçe güncellenecek.

## 1. Temel Problem

Semantik benzerlik ile mizahi uygunluk aynı şey değildir. Embedding modelleri **konuya** bakar, meme seçimi ise **duruma ve tepkiye** bakar.

> Girdi: *"Patron toplantıyı cuma 17:55'e koydu"*
>
> - Semantik arama: içinde "patron", "ofis", "toplantı" geçen meme'ler (çoğu alakasız).
> - Doğru cevap: "bıkkın kabulleniş" ya da "hayırdır inşallah" tepkisi veren, ofisle hiç ilgisi olmayan bir meme.

**Ana fikir:** Sorguyu ve meme'i aynı soyut "durum uzayına" taşıyıp karşılaştırmayı orada yapmak. Meme tarafında bu, insan tarafından yazılan durum, duygu, niyet ve örnek kullanım alanlarıyla sağlanır. Sorgu tarafında ise girdi aynı alanlara soyutlanır.

## 2. Alınan Kararlar

| Konu | Karar |
| --- | --- |
| Veri | Kendi topladığımız ~300 meme |
| Etiketleme | Anlam alanları tamamen elle, anlamı insan yazar. Görsel tarifin taslağını VLM üretir, insan düzeltir. |
| Annotation platformu | İleride geliştirilecek. Şema bu dokümandaki gibi. |
| VLM açıklaması | Zorunlu. Yükleme sırasında VLM görselde ne olduğunu yorumsuz tarif eder, annotator kontrol edip düzeltir. Tarif modunda kullanılır. |
| Anahtar kelimeler | Her meme'e 3–8 düz Türkçe anahtar kelime. BM25'te kullanılır. Hashtag ve bitişik yazım yok. |
| Ton | Ayrı bir alan yok. Ton mevcut etiketlere eşlenir (bkz. 4.1). |
| OCR | Opsiyonel |
| Örnek durum genişletme (LLM) | Opsiyonel. LLM bağlamı tahmin etmez, insanın yazdığı bağlamı çoğaltır. |
| Görsel embedding (CLIP/SigLIP) | Aramada yok. Sadece veri toplarken kopya tespiti için kullanılabilir. |
| Baseline'lar | BM25, düz semantik arama, çok vektörlü LLM'siz arama (B2), bütün kartlar bağlamda LLM |
| Hız ve maliyet | Her sistem için p50/p95 gecikme ve sorgu başı maliyet ölçülür (bkz. 6). |
| Geri besleme | Kullanıcı seçimleri ileride "geçmiş sorgular" alanına eklenecek |

## 3. Annotation Şeması

```yaml
id: kemal-sunal-hayirdir
gorsel: memes/kemal-sunal-hayirdir.jpg
tur: template                  # template | hazir_meme
ad: "Hayırdır inşallah"
kaynak: "Kemal Sunal, <film adı>"   # eser / karakter / sahne

# --- Görsel tarif (VLM taslağı, insan düzeltir) ---
vlm_aciklama: >                 # sadece görselde görünenler, yorum yok
  <kişi, yüz ifadesi, nesneler, sahne, görseldeki yazı>

# --- Anlam alanları (insan yazar) ---
durum: >                        # soyut durum iskeleti
  Beklenmedik, şüpheli ya da tuhaf bir teklif veya davranış karşısında
  temkinli şaşkınlık.
ornek_durumlar:                 # 3–5 somut örnek
  - "Patron cuma akşamı 'bir dakika gelir misin' yazdı"
  - "Hiç konuşmadığın biri 'naber kanka' diye mesaj attı"
uygun_olmayan_durumlar:         # 1–2 örnek
  - "Arkadaşın gerçekten kötü bir haber verdiğinde"
kulturel_bilgi: >               # gereken arka plan + neden komik
  ...
anahtar_kelimeler:              # 3–8 adet, düz Türkçe; BM25'te kullanılır
  - "hayırdır"
  - "şüpheli bakış"
  - "işkillenmek"
duygu: [suphe, saskinlik]       # sabit listeden, sistem adlarıyla (bkz. 3.1)
niyet: [tepki_gosterme]         # sabit listeden
mekanizma: [ironi]              # sabit listeden
uyari: []                       # politik | kaba_argo | hassas; [] = "uyarı yok" onayı
notlar: ""

# --- Kayıt bilgisi (gold.jsonl) ---
annotator: ["a1"]               # takma adla liste; çift etiketli meme'de iki kişi
reviewer: "a2"                  # onaylayan kişi; tek etiketli meme'de ikinci bakışı yapan
sema_versiyonu: "1.0"
etiket_listesi_versiyonu: "1.0"

# --- Opsiyonel, annotation sonrası denenecek ---
ocr_metin: null                 # görseldeki yazı
genisletilmis_durumlar: null    # LLM ile örnek durum çoğaltma
gecmis_sorgular: null           # kullanıcı seçimlerinden (ileride)
```

### 3.1 Etiket Listeleri (taslak)

Listeler etiketleme kılavuzunda her biri için kısa tanım ve örnekle birlikte sabitlenecek. Her etiketin değişmeyen bir sistem adı (küçük harf, Türkçe karaktersiz, boşluk yerine alt çizgi: `tepki_gosterme`) ve ekranda görünen bir adı ("Tepki gösterme") vardır ([ADR-0008](adr/0008-etiket-sistem-adlari.md)). Eğik çizgili etiketler tek kavramdır ve birleşik adla tutulur: `sevinc_zafer`, `ustunluk_kibir`, `sikayet_isyan`, `kaba_argo`.

| Alan | Etiketler |
| --- | --- |
| **duygu** | bıkkınlık, şaşkınlık, şüphe, sevinç/zafer, utanç, öfke, çaresizlik, üstünlük/kibir, hayal kırıklığı, panik, sevimlilik, umursamazlık |
| **niyet** | onaylama, reddetme, alay etme, tepki gösterme, kendiyle dalga geçme, şikayet/isyan, övme, uyarma, kabullenme, geçiştirme |
| **mekanizma** | ironi, abartı, absürt, beklenti–gerçeklik zıtlığı, kendini küçümseme, karşılaştırma (A vs B), bariz olanı söyleme, kültürel gönderme |
| **uyari** | politik, kaba/argo, hassas (din, ölüm, etnik köken vb.) |

Uyarı etiketi filtreleme için değil, sadece işaretleme için kullanılır.

### 3.2 Etiketleme Kuralları

- Etiketleme kılavuzu (tanımlar ve örnekler) etiketlemeye başlamadan önce yazılır.
- `ornek_durumlar` kullanıcının gerçekte yazacağı dille yazılır: kısa, gündelik, gerekiyorsa argolu. Örneğin "akademik başarım düştü" değil, "finaller içimden geçti".
- `vlm_aciklama` yalnızca görselde görüneni anlatır. Duygu, yorum ve kullanım bağlamı anlam alanlarına yazılır.
- `anahtar_kelimeler` düz Türkçe ve Türkçe karakterle yazılır: meme'in bilinen adı, replik, karakter, görünen nesne, argo karşılıklar. Hashtag ya da bitişik yazım kullanılmaz ("#hayalkirikligi" değil, "hayal kırıklığı").
- Meme'lerin bir alt kümesi iki kişiye ayrı ayrı etiketletilir ve uyum ölçülür (tek etiketli alanlarda Cohen's kappa, çok etiketli alanlarda Krippendorff's alpha).
- Kalan meme'leri tek kişi etiketler; onları etiketlemeyen bir reviewer da hafif bir ikinci bakışla kontrol eder ([ADR-0014](adr/0014-tek-etiketli-memelerde-ikinci-bakis.md)). Böylece her meme en az iki kişiden geçer.
- Test sorgularını, o meme'lerin gold kaydına katkı veren kişiler (annotator'lar ve reviewer) yazmaz. Bu, sonuçların olduğundan iyi görünmesini önler ([ADR-0002](adr/0002-sizinti-kurali-reviewer-dahil.md)).

## 4. Sorgu Akışı

```
Girdi (durum / konuşma / tarif)
        │
        ▼
   Router Agent ──► Tarif ──► Dense: vlm_aciklama
        │                     BM25: ad, kaynak, anahtar_kelimeler, kültürel bilgi (+ OCR varsa)
        │                     → RRF → ilk 5 sonuç + "daha fazla göster" (bkz. 4.2)
        │
        ▼ Durum / konuşma
   Context Agent
   ├─ Durum: yüzeydeki varlıkları atıp iskeleti çıkarır (step-back)
   ├─ Duygu ve niyet: şemadaki sabit listelerle aynı etiketler
   ├─ İstenen ton (alaycı / sevimli / kaba): 4.1'deki eşlemeyle etiketlere çevrilir
   └─ HyDE: "bu meme şu durumda kullanılır" cümlesi
        │
        ▼
   Hybrid arama
   ├─ Dense: durum + HyDE ↔ durum, örnek_durumlar
   ├─ Sparse / BM25: ad, kaynak, kültürel bilgi, anahtar_kelimeler
   ├─ Duygu / niyet eşleşmesine göre puan artırma
   └─ uygun_olmayan_durumlar ile benzerliğe göre puan düşürme
        │
        ▼
   RRF ile birleştirme → ilk ~30 aday
        │
        ▼
   LLM Reranker (mizah yargısı)
   "Bu meme bu duruma cevap olarak uygun ve komik mi? Neden?"
   → sıralama + kültürel bilgiye dayanan "neden bu meme" açıklaması + uyarı etiketi
        │
        ▼
   Kullanıcı ──► geri bildirim ("daha alaycı olsun", "daha az kaba")
        │
        └─► Refine: hedef duygu/niyet/tonu güncelle, sorguyu yeniden yaz, tekrar ara
```

İş bölümü: retrieval yalnızca recall'u sağlar (doğru meme ilk 30'a girsin), mizah yargısını reranker verir.

### 4.1 Ton eşlemesi

Ton için şemada ayrı bir alan yok. Context Agent'ın çıkardığı ton ve kullanıcının refine istekleri mevcut etiketlere çevrilir:

| Ton | Şemadaki karşılığı | Refine'da kullanımı |
| --- | --- | --- |
| alaycı | niyet: alay etme | "daha alaycı olsun" → bu etiketin puan artırması yükselir |
| kaba | uyarı: kaba/argo | "daha az kaba olsun" → bu uyarıyı taşıyan meme'lerin puanı düşer (filtrelenmez) |
| sevimli | duygu: sevimlilik | "daha sevimli olsun" → bu etiketin puan artırması yükselir |

### 4.2 Sonuç listesi

- **Durum modu:** Reranker'ın sıraladığı ilk 5 meme. Her birinin yanında "neden bu meme" açıklaması ve varsa uyarı etiketi gösterilir.
- **Tarif modu:** İlk 5 sonuç gösterilir. "Daha fazla göster" ile aday listesinin devamı (ilk ~30'a kadar) açılır. Sabit bir benzerlik eşiği kullanılmaz.

## 5. Teknik Seçenekler

| Bileşen | Seçim | Not |
| --- | --- | --- |
| Embedding | `bge-m3` | Çok dilli, dense + sparse tek modelde |
| Vector DB | Qdrant | Adlandırılmış vektörler, payload filtresi, RRF ile hybrid sorgu. Alternatif: pgvector |
| BM25 / Türkçe | bge-m3 sparse veya Zemberek ile kök bulma | "toplantıyı" ↔ "toplantı" eşleşmesi için |
| Reranker | LLM | Alternatif hızlı seçenek: `bge-reranker-v2-m3` |
| VLM | Zorunlu | Görsel tarif taslağı. Model seçimi açık soru (bkz. 8) |
| OCR | Opsiyonel | Bkz. Kararlar |
| CLIP / SigLIP | Opsiyonel | Sadece kopya tespiti |

## 6. Değerlendirme

**Karşılaştırılacak sistemler**

| Sistem | Açıklama |
| --- | --- |
| A. BM25 | Anahtar kelime araması |
| B. Düz semantik arama | Sorgu embedding'i ↔ meme embedding'i |
| B2. Çok vektörlü arama (LLM'siz) | `vlm_aciklama` ile `durum` + `ornek_durumlar` ayrı vektörlerde aranır; `ad`, `kaynak`, `kulturel_bilgi`, `anahtar_kelimeler` BM25'te. Sonuçlar RRF ile birleştirilir, uygun olmayan durum cezası uygulanır. Mod ayrımı ve LLM çağrısı yoktur. |
| C. Agentic retrieval | Bölüm 4'teki akış |
| D. Bütün kartlar bağlamda | 300 meme kartının hepsi LLM'e verilir, LLM seçer |

**Test seti:** ~100 durum/konuşma. Her biri için bir veya daha fazla doğru meme, annotator olmayan kişiler tarafından işaretlenir.

**Parafraz alt kümesi:** 20 sorgu, her biri 2 farklı yazımla daha yazılır (devrik cümle, argolu/resmi, kısa/uzun). Varyantlar aynı doğru meme'leri paylaşır. Böylece sistemin aynı durumu farklı yazımlarda ne kadar tutarlı bulduğu ölçülür.

**Metrikler**
- Recall@1 / @5 / @10, MRR, nDCG@10
- İnsan puanlaması: önerilen meme'in uygunluğu ve komikliği (1–5)
- Uyarı etiketi doğruluğu
- Gecikme: sorgu başına uçtan uca süre, p50 ve p95
- Maliyet: sorgu başına LLM API maliyeti (A, B ve B2'de LLM çağrısı yok)
- Parafraz tutarlılığı: aynı gruptaki varyantlar arasında Recall@5 ve MRR farkı

**Ablation:** C sistemine bileşenler tek tek eklenip çıkarılarak ölçülür: HyDE, uygun olmayan durum cezası, duygu/niyet artırması, LLM reranker, VLM açıklaması, OCR, örnek durum genişletme. B2, C'den bütün LLM adımları çıkarıldığında kalan sistemdir ve bu ablation'ın alt sınırı olarak okunur.

**Ek deney:** Aynı meme'ler LLM'e otomatik etiketletilip insan etiketleriyle karşılaştırılır ("LLM Türk meme bağlamını ne kadar biliyor?").

## 7. İleride

- Annotation platformu
- Kullanıcı seçimlerinin `gecmis_sorgular` alanına geri beslenmesi
- Gerekirse görsel embedding (Tarif modunda başarısız sorgular çıkarsa)
- Seçilen template için Türkçe caption üretimi

## 8. Açık Sorular

- Etiket listelerinin son hali
- Kaç kişi etiketleyecek, meme'ler nasıl bölünecek?
- Hangi LLM ve VLM kullanılacak (Context Agent, HyDE, reranker, görsel tarif taslağı)?
- Veri setini yayınlayacak mıyız? Yayınlanırsa görseller yerine sadece etiketler ve kaynak linkleri paylaşılmalı.

## 9. Değerlendirilip Alınmayan Öneriler

Ekim 2026'da ekip içinde önerilen, değerlendirildikten sonra alınmayan seçenekler:

| Öneri | Neden alınmadı |
| --- | --- |
| Arama anında hiç LLM çalıştırmamak | Context Agent, HyDE, reranker, açıklama ve refine döngüsü olmadan BRIEF'teki farklılaştırıcılar ve başarı ölçütü boşa düşer. Fikir B2 baseline olarak ölçülüyor. |
| Bütün etiketlemeyi tek kişinin yapması, diğerlerinin 1–5 puan vermesi | Etiketleyiciler arası uyum ölçülemez. Tanıdıklığı düşük meme'leri devredecek kimse kalmaz. Toplam iş de azalmaz (300 etiket + 900 puanlama). Üslup tutarlılığı kılavuz ve kalibrasyon turuyla sağlanır. |
| Anlam alanlarını LLM'e ön-doldurtmak | Etiketleyici taslağa kayar, çift etiketlemede uyum yapay olarak yükselir, LLM ile insan etiketlerini karşılaştıran deney kirlenir. LLM yalnızca görsel tarifin taslağını üretir. |
| Kara liste ya da sınıflandırıcıyla içerik engelleme (veri, etiket, sorgu) | BRIEF'e göre uyarı etiketi var, otomatik engelleme kapsam dışı. Argo anlamak temel hedef ve yapıştırılan konuşmalar çoğu zaman küfür içerir. Engelleme, uyarı etiketini ve doğruluk metriğini anlamsızlaştırır. |
| Sorgu türünü kelime listesiyle tahmin edip sabit ağırlık vermek | Durum sorgularında da somut nesneler geçer ("kedim bardağı düşürdü"). Ağırlıklar keyfi kalır. Mod ayrımını Router Agent, birleştirmeyi RRF yapar. |
| Benzer meme'leri farklı konulara bağlamak | Meme konuya değil tepkiye bağlıdır (bkz. 1). |
| Zıt duyguların aynı kayıtta bulunmaması | İronik meme'ler zıt duyguları birlikte taşır; `mekanizma` alanı bunun için var. |
| Embedding metinlerinden bağlaç ve dolgu kelimeleri temizlemek | Dense modeller doğal cümlelerle eğitilir; sorgular da doğal cümle. |
| GIF desteği, 500–1000 meme | GIF kapsam dışı (BRIEF). Elle etiketlemede ~300 meme hedefi korunur. |
| Kullanıcıya hazır sorgu listesi sunmak | Konuşma yapıştırma modunu engeller. Fikrin özü parafraz testi olarak alındı (bkz. 6). |
| Meme seçimini sınıflandırıcıyla yapmak | ~300 sınıf için eğitim verisi yok; problem bir retrieval problemi. |

## 10. İlgili Çalışmalar

- [MemeCMD](https://arxiv.org/abs/2507.00891): sohbet bağlamına göre meme seçimi. Uygun/uygun olmayan durum, duygu ve niyet alanları.
- [PerSRV](https://arxiv.org/abs/2410.21801): sticker arama. BM25, geçmiş sorgular, VLM ablation'ı.
- [MemeBench](https://arxiv.org/abs/2607.27798): görsel-dil modellerinin kültüre bağlı meme'lerdeki bilgi açığı.
- [MemeMatch](https://ojs.aaai.org/index.php/ICWSM/article/view/42785): yerel (metin) ve genel (template) bağlamın ayrı temsili.
- [SRS / StickerChat](https://arxiv.org/abs/2003.04679), [MOD](https://arxiv.org/abs/2203.03835): diyalogda sticker/meme yanıt seçimi.
- Teknikler: HyDE (Gao vd., 2022), doc2query (Nogueira vd., 2019), step-back prompting (Zheng vd., 2023), RRF (Cormack vd., 2009).
