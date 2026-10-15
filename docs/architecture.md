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
| Etiketleme | Tamamen elle. Anlamı insan yazar. |
| Annotation platformu | İleride geliştirilecek. Şema bu dokümandaki gibi. |
| VLM açıklaması | Opsiyonel, annotation bittikten sonra katkısı ölçülecek |
| OCR | Opsiyonel |
| Örnek durum genişletme (LLM) | Opsiyonel. LLM bağlamı tahmin etmez, insanın yazdığı bağlamı çoğaltır. |
| Görsel embedding (CLIP/SigLIP) | Aramada yok. Sadece veri toplarken kopya tespiti için kullanılabilir. |
| Baseline'lar | BM25, düz semantik arama, bütün kartlar bağlamda LLM |
| Geri besleme | Kullanıcı seçimleri ileride "geçmiş sorgular" alanına eklenecek |

## 3. Annotation Şeması

```yaml
id: kemal-sunal-hayirdir
gorsel: memes/kemal-sunal-hayirdir.jpg
tur: template                  # template | hazir_meme
ad: "Hayırdır inşallah"
kaynak: "Kemal Sunal, <film adı>"   # eser / karakter / sahne

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
duygu: [suphe, saskinlik]       # sabit listeden (bkz. 3.1)
niyet: [tepki]                  # sabit listeden
mekanizma: [ironi]              # sabit listeden
uyari: []                       # politik | kaba | hassas
notlar: ""
annotator: "<etiketleyen>"

# --- Opsiyonel, annotation sonrası denenecek ---
vlm_aciklama: null              # VLM ile literal görsel açıklaması
ocr_metin: null                 # görseldeki yazı
genisletilmis_durumlar: null    # LLM ile örnek durum çoğaltma
gecmis_sorgular: null           # kullanıcı seçimlerinden (ileride)
```

### 3.1 Etiket Listeleri (taslak)

Listeler etiketleme kılavuzunda her biri için kısa tanım ve örnekle birlikte sabitlenecek.

| Alan | Etiketler |
| --- | --- |
| **duygu** | bıkkınlık, şaşkınlık, şüphe, sevinç/zafer, utanç, öfke, çaresizlik, üstünlük/kibir, hayal kırıklığı, panik, sevimlilik, umursamazlık |
| **niyet** | onaylama, reddetme, alay etme, tepki gösterme, kendiyle dalga geçme, şikayet/isyan, övme, uyarma, kabullenme, geçiştirme |
| **mekanizma** | ironi, abartı, absürt, beklenti–gerçeklik zıtlığı, kendini küçümseme, karşılaştırma (A vs B), bariz olanı söyleme, kültürel gönderme |
| **uyari** | politik, kaba/argo, hassas (din, ölüm, etnik köken vb.) |

Uyarı etiketi filtreleme için değil, sadece işaretleme için kullanılır.

### 3.2 Etiketleme Kuralları

- Etiketleme kılavuzu (tanımlar ve örnekler) etiketlemeye başlamadan önce yazılır.
- Meme'lerin bir alt kümesi iki kişiye ayrı ayrı etiketletilir ve uyum ölçülür (tek etiketli alanlarda Cohen's kappa, çok etiketli alanlarda Krippendorff's alpha).
- Test sorgularını, o meme'lerin örnek durumlarını yazan kişiler yazmaz. Bu, sonuçların olduğundan iyi görünmesini önler.

## 4. Sorgu Akışı

```
Girdi (durum / konuşma / tarif)
        │
        ▼
   Router Agent ──► Tarif ──► ad + kaynak + kültürel bilgi (+ OCR/VLM varsa) araması
        │
        ▼ Durum / konuşma
   Context Agent
   ├─ Durum: yüzeydeki varlıkları atıp iskeleti çıkarır (step-back)
   ├─ Duygu ve niyet: şemadaki sabit listelerle aynı etiketler
   ├─ İstenen ton (alaycı / sevimli / sert)
   └─ HyDE: "bu meme şu durumda kullanılır" cümlesi
        │
        ▼
   Hybrid arama
   ├─ Dense: durum + HyDE ↔ durum, örnek_durumlar
   ├─ Sparse / BM25: ad, kaynak, kültürel bilgi, anahtar kelimeler
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

### 4.1 İki Modun Sonuç Döndürme Farkı

1. **Durum / Reaksiyon Modu (`mod=durum`):**
   - **Hedef:** Sohbet/konuşma bağlamına en uygun mizahi reaksiyonu vermek.
   - **Çıktı:** Reranker tarafından elenmiş ve gerekçelendirilmiş **Top-5** meme.

2. **Görsel Tarif Modu (`mod=tarif`):**
   - **Hedef:** Kullanıcının aklında kalan spesifik bir görseli bulmasını sağlamak (Katalog/Arama Motoru davranışı).
   - **Çıktı:** Aday kısıtlaması yoktur. Görsel benzerlik skoru ($V_{visual}$) en yüksek olandan en düşüğe doğru **tüm veri seti sıralı liste (sayfalamalı/infinite scroll)** olarak sunulur.
   - **Tükenme Durumu:** Belirlenen taban benzerlik eşiğinin altına inildiğinde veya liste bittiğinde kullanıcıya *"Aradığınız meme veri setinde bulunamadı"* bilgisi verilir.

## 5. Teknik Seçenekler

| Bileşen | Seçim | Not |
| --- | --- | --- |
| Embedding | `bge-m3` | Çok dilli, dense + sparse tek modelde |
| Vector DB | Qdrant | Adlandırılmış vektörler, payload filtresi, RRF ile hybrid sorgu. Alternatif: pgvector |
| BM25 / Türkçe | bge-m3 sparse veya Zemberek ile kök bulma | "toplantıyı" ↔ "toplantı" eşleşmesi için |
| Reranker | LLM | Alternatif hızlı seçenek: `bge-reranker-v2-m3` |
| VLM / OCR | Opsiyonel | Bkz. Kararlar |
| CLIP / SigLIP | Opsiyonel | Sadece kopya tespiti |

## 6. Değerlendirme

**Karşılaştırılacak sistemler**

| Sistem | Açıklama |
| --- | --- |
| A. BM25 | Anahtar kelime araması |
| B. Düz semantik arama | Sorgu embedding'i ↔ meme embedding'i |
| C. Agentic retrieval | Bölüm 4'teki akış |
| D. Bütün kartlar bağlamda | 300 meme kartının hepsi LLM'e verilir, LLM seçer |

**Test seti:** ~100 durum/konuşma. Her biri için bir veya daha fazla doğru meme, annotator olmayan kişiler tarafından işaretlenir.

**Metrikler**
- Recall@1 / @5 / @10, MRR, nDCG@10
- İnsan puanlaması: önerilen meme'in uygunluğu ve komikliği (1–5)
- Uyarı etiketi doğruluğu

**Ablation:** C sistemine bileşenler tek tek eklenip çıkarılarak ölçülür: HyDE, uygun olmayan durum cezası, duygu/niyet artırması, LLM reranker, VLM açıklaması, OCR, örnek durum genişletme.

**Ek deney:** Aynı meme'ler LLM'e otomatik etiketletilip insan etiketleriyle karşılaştırılır ("LLM Türk meme bağlamını ne kadar biliyor?").

## 7. İleride

- Annotation platformu
- Kullanıcı seçimlerinin `gecmis_sorgular` alanına geri beslenmesi
- Gerekirse görsel embedding (Tarif modunda başarısız sorgular çıkarsa)
- Seçilen template için Türkçe caption üretimi

## 8. Açık Sorular

- Etiket listelerinin son hali
- Kaç kişi etiketleyecek, meme'ler nasıl bölünecek?
- Hangi LLM sağlayıcısı kullanılacak (Context Agent, HyDE, reranker)?
- Veri setini yayınlayacak mıyız? Yayınlanırsa görseller yerine sadece etiketler ve kaynak linkleri paylaşılmalı.

## 9. İlgili Çalışmalar

- [MemeCMD](https://arxiv.org/abs/2507.00891): sohbet bağlamına göre meme seçimi. Uygun/uygun olmayan durum, duygu ve niyet alanları.
- [PerSRV](https://arxiv.org/abs/2410.21801): sticker arama. BM25, geçmiş sorgular, VLM ablation'ı.
- [MemeBench](https://arxiv.org/abs/2607.27798): görsel-dil modellerinin kültüre bağlı meme'lerdeki bilgi açığı.
- [MemeMatch](https://ojs.aaai.org/index.php/ICWSM/article/view/42785): yerel (metin) ve genel (template) bağlamın ayrı temsili.
- [SRS / StickerChat](https://arxiv.org/abs/2003.04679), [MOD](https://arxiv.org/abs/2203.03835): diyalogda sticker/meme yanıt seçimi.
- Teknikler: HyDE (Gao vd., 2022), doc2query (Nogueira vd., 2019), step-back prompting (Zheng vd., 2023), RRF (Cormack vd., 2009).
