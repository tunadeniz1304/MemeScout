# MemeScout — Annotation Platformu ve Veri Şartnamesi

> **Durum:** Güncellendi (ADR-0001 — ADR-0008, Çoklu Vektör ve Tekil Annotator Entegrasyonu)  
> **İlgili Dokümanlar:** [architecture.md](http://architecture.md), [openapi.yaml](../openapi.yaml), [docs/annotation\_design.txt](http://annotation_design.txt)

---

## 1\. Amaç ve Kapsam

* **Veri Hacmi:** \~300–500 yerli/uluslararası meme şablonu ve animasyonlu GIF.  
* **Etiketleme Modeli (Tekil Annotator \+ Çapraz Denetim):** Çoklu etiketleyicilerin yaratacağı üslup uyuşmazlığını ve veri kirliliğini önlemek adına tüm veri kümesi **tek bir birincil annotator** tarafından tutarlı bir dil ve standartla etiketlenir. Ekibin diğer 3 üyesi izleyici, denetçi ve test sorgusu yazarı olarak görev yapar.  
* **Çoklu Vektör İllüzyonu (Zero-LLM Runtime):** Arama anında yüksek gecikme (latency) ve maliyet yaratan generative LLM'ler her sorguda çalıştırılmaz. Dilin mizahi boyutu; zenginleştirilmiş soyut durum tanımları, pozitif/negatif senaryolar, sokak dili/slang enjeksiyonu ve Türkçe dense embedding (`bge-m3`, `ytu-ce-cosmos`) modellerinin latent uzay yakınsamasıyla çözülür.  
* **Platform Çıktıları:**  
  1. `gold.jsonl`: Çift vektörlü (`V_visual`, `V_context`) arama motoruna doğrudan beslenen kesinleşmiş kayıtlar.  
  2. `annotations_raw.jsonl`: Denetim izleri, revizyonlar ve annotator süreç telemetrisi.  
  3. `test_set.jsonl`: Sızıntı kurallarına tam uyumlu bağımsız doğrulama seti.

---

## 2\. Roller ve Yetki Matrisi

| Rol | Kullanıcılar | Yetkiler | Kısıtlar |
| :---- | :---- | :---- | :---- |
| **Annotator** | Tek Kişi (1) | Meme'leri hem fiziksel hem bağlamsal boyutlarıyla etiketler, taslak kaydeder, teslim eder. | Başka etiketleyicilerle çakışma yaşamaz; tekil sorumludur. |
| **Reviewer / Viewer** | Ekip Üyeleri (3) | Etiketleri görüntüler, yorum/işaret (`/comments`) bırakır, revizyon talep eder. | Alan verilerini doğrudan ezemez; test sorgusu yazarıdır. |
| **Admin** | Sistem / Yükleyici | Meme/GIF yükler, etiket listelerini günceller, `gold.jsonl` dışa aktarımı alır. | — |

---

## 3\. Veri Modeli

Meme (1) ───\< (1) Annotation (Tekil Annotator) ─── (1) Kullanıcı

 │                     │

 │                     └── versiyonlar (İyimser Kilitleme / surum)

 ├── (1) GoldKayıt

 ├── (\*) Yorum / İşaret (Ekip İçi Tartışma & Hata Bildirimi)

 └── (\*) TestSorgusu (Sızıntı Korumalı Doğrulama Seti)

### 3.1 Meme (Görsel ve Dosya Bilgisi)

Platform yükleme anında otomatik hesaplar; kullanıcı yalnızca görseli yükler:

| Alan | Tip | Açıklama |
| :---- | :---- | :---- |
| `id` | `string` | Benzersiz kimlik (dosya adı veya slug formatında) |
| `gorsel_yolu` | `string` | Dosyanın sunucu dosya sistemindeki konumu (`memes/...`) |
| `medya_tipi` | `enum` | `image` veya `gif` |
| `sha256` | `string` | Mükerrer dosya yüklemelerini önleyen dosya karması |
| `yukleyen` | `kullanici` | Aktarımı başlatan kullanıcı hesabı |
| `yuklenme_zamani` | `datetime` | UTC zaman damgası |

---

### 3.2 Annotation (İçerik Şeması — Çoklu Vektör ve Alan Ağırlıklandırma)

Arama anında görsel tarif aramaları ile durumsal reaksiyon aramalarını tam isabetle ayrıştırmak için alanlar fiziksel ve bağlamsal olarak yapılandırılmıştır:

| Alan Adı | Tip | Zorunlu | Karakter / Adet Sınırı | Hedef Vektör / Amaç | Doğrulama & Format Kuralı |
| :---- | :---- | :---: | :---: | :---- | :---- |
| `tur` | `enum` | ✓ | — | Filtreleme | `template` veya `hazir_meme` |
| `ad` | `string` | ✓ | Min 3, Max 60 | Keyword / Sparse | Meme'in yaygın bilinen Türkçe adı |
| `kaynak` | `string` | — | Max 100 | Keyword / Sparse | Eser, film, dizi, sahne veya köken |
| `gorsel_tanim` | `metin` | ✓ | **Min 20, Max 120** | **`V_visual`** | **Yalnızca kameranın gördüğü somut nesneler/varlıklar.** Duygu ve soyut yorum YAZILMAZ. |
| `durum` | `metin` | ✓ | **Min 30, Max 150** | **`V_context` (Çekirdek)** | Yüzeydeki nesnelerden arındırılmış soyut duygu ve tepki iskeleti. |
| `ornek_durumlar` | `liste` | ✓ | **3–5 adet** | **`V_context` (Pozitif)** | Meme'in tam karşılık geldiği somut hayat senaryoları. |
| `uygun_olmayan_durumlar` | `liste` | ✓ | **1–2 adet** | **`V_negative` (Ceza)** | Meme'in asla atılmaması gereken durumlar (Negatif ceza puanı). |
| `es_anlam_ve_slang` | `liste` | ✓ | **3–8 kelime** | **`V_context` (Manipülasyon)** | Sokak dili, argo, deyimler (`["bıkmak", "patlamak", "vizeler"]`). |
| `kulturel_bilgi` | `metin` | ✓ | Min 30, Max 250 | Reranker / Explain | Neden komik olduğu ve yerli kültürdeki karşılığı. |
| `duygu` | `liste` | ✓ | 1–3 etiket | Filtre / Boost | Sabit listeden (ADR-0008 snake\_case: `bikkinlik`, `suphe` vb.) |
| `niyet` | `liste` | ✓ | 1–3 etiket | Filtre / Boost | Sabit listeden (`sikayet_isyan`, `alay_etme`, `kabullenme` vb.) |
| `mekanizma` | `liste` | ✓ | 1–3 etiket | Filtre / Boost | Sabit listeden (`ironi`, `abarti`, `beklenti_gerceklik_zitligi` vb.) |
| `uyari` | `liste` | ✓ | ADR-0004 | Güvenlik Etiketi | `null` (gönderilemez), `[]` (uyarı yok), `["politik", "kaba_argo", "hassas"]` |
| `notlar` | `metin` | — | Max 300 | İç Takip | Annotator serbest not alanı |

---

### 3.3 Arama Motoru Puanlama Formülü (Ceza Destekli Hibrit Arama)

Metinler vektör motoruna 3 farklı bileşen olarak sunulur:

* `TEXT_FOR_V_VISUAL` \= `gorsel_tanim`  
* `TEXT_FOR_V_CONTEXT` \= `durum` \+ `ornek_durumlar` \+ `es_anlam_ve_slang`  
* `TEXT_FOR_V_NEGATIVE` \= `uygun_olmayan_durumlar`

Kullanıcı sorgusu \$q\$ için kosinüs yakınlıkları üzerinden nihai alaka skoru hesaplanır:

\$\$\\text{Final\_Score} \= (W\_{visual} \\cdot S\_{visual}) \+ (W\_{context} \\cdot S\_{context}) \- (\\lambda \\cdot P\_{negative})\$\$

* **Tarif Modu:** \$W\_{visual} \= 0.70\$, \$W\_{context} \= 0.30\$  
* **Durum Modu:** \$W\_{visual} \= 0.20\$, \$W\_{context} \= 0.80\$  
* **Ceza Katsayısı:** \$\\lambda \\approx 0.25\$

---

### 3.4 Annotation Süreç Bilgisi ve İyimser Kilitleme

| Alan | Tip | Açıklama |
| :---- | :---- | :---- |
| `annotator` | `kullanici` | Etiketleyen birincil kullanıcı |
| `durum_kodu` | `enum` | Yaşam döngüsü statüsü (§4.2) |
| `surum` | `int` | **İyimser Kilitleme (ADR-0005):** Taslakta artar, çakışmada `409` döner. |
| `revizyon_notu` | `metin` | Denetçilerin bıraktığı düzeltme talimatı |
| `tanidiklik` | `1–5` | 1–2 puan alan meme başka bağlama aktarılır veya tartışmaya açılır. |
| `harcanan_sure_sn` | `int` | Sayfa etkileşimdeyken ölçülen aktif süre |

---

### 3.5 Test Sorgusu ve Sızıntı (Leakage) Koruması (ADR-0002)

| Alan | Tip | Açıklama |
| :---- | :---- | :---- |
| `id`, `metin` | `string` | Kullanıcı konuşması veya meme tarifi |
| `mod` | `enum` | `durum` veya `tarif` |
| `dogru_memeler` | `liste` | Eşleşmesi gereken doğru meme kimlikleri (`id`) |
| `yazan` | `kullanici` | Sorguyu oluşturan ekip üyesi |

> **Katı Sızıntı Kuralı:** Test setindeki \~100 sorguyu **yalnızca annotator olmayan diğer 3 ekip üyesi yazar**. Annotator'ın kendi yazdığı `ornek_durumlar` üzerinden test sorgusu oluşturması sistem seviyesinde engellenir (`422 SIZINTI`).

---

## 4\. Etiketleme Yaşam Döngüsü ve İş Akışı

### 4.1 Aşamalar

1. **Ön Hazırlık:** ADR-0008 standartlarındaki sabit etiket listeleri sisteme tanımlanır.  
2. **Tek Elden Giriş:** Birincil annotator tüm görselleri sırayla açar; görsel tarifi ve durum iskeletini bağımsız bloklar halinde doldurur.  
3. **Akıllı Enjeksiyon:** Gerçekçi kullanım senaryoları (`ornek_durumlar`), ceza senaryoları (`uygun_olmayan_durumlar`) ve sokak argosu eklenir.  
4. **Ekip Denetimi:** Diğer 3 üye etiketleri inceler; kültürel veya mantıksal bir eksiklik görürse yorum bırakır veya revizyon ister.  
5. **Dışa Aktarım:** Onaylanan kayıtlar doğrudan `gold.jsonl` olarak derlenir ve çift vektörlü arama indeksine aktarılır.

### 4.2 Durum Geçişleri

atanmadi ──► atandi ──► devam\_ediyor ──► gonderildi ──┬──► onaylandi (gold)

                             ▲                        │

                             └─── revizyon\_gerekli ◄──┘

| Endpoint | Geçiş | Açıklama |
| :---- | :---- | :---- |
| `POST /annotations/{id}/start` | `atandi → devam_ediyor` | Etiketleme işlemi başlar |
| `POST /annotations/{id}/submit` | `devam_ediyor → gonderildi` | Form doğrulanır ve teslim edilir |
| `POST /annotations/{id}/request-revision` | `gonderildi → revizyon_gerekli` | Denetçi düzeltme talep eder |
| `POST /reviews/{meme_id}/gold` | `gonderildi → onaylandi` | Kayıt kesinleşir ve gold olur |

---

## 5\. Platform Kullanıcı Deneyimi (UI / UX) Kuralları

* **Ayrılmış Çift Form Düzeni:** Form ekranında `Fiziksel Görsel Tarif` alanı ile `Kullanım Durumu & Slang` alanları belirgin renk bloklarıyla ayrılır; annotator'ın nesne ile soyut duyguyu karıştırması önlenir.  
* **Canlı Doğrulama & Sayaçlar:** `Min` ve `Max` sınırları klavyeden yazıldığı anda kontrol edilir; sınır aşımında veya yetersiz karakterde uyarı belirir.  
* **"Uyarı Yok" Onay Kutusu (ADR-0004):** Arayüzde uyarı etiketlerinin yanında bağımsız bir "Uyarı yok" checkbox'ı bulunur; işaretlenmeden `uyari: []` gönderilemez.  
* **Kesintisiz Taslak:** Her 5 saniyede bir ve sekme kapanırken `PATCH /annotations/{id}/draft` çağrılır (`surum` çakışması korumalı).  
* **Mükerrerlik Kalkanı:** Yeni bir görsel yüklendiğinde anlık SHA-256 taraması yapılır; kopya varsa yükleme engellenir.

---

## 6\. Dışa Aktarım Formatı (`gold.jsonl`)

Arama motorunun doğrudan okuduğu satır bazlı JSON yapısı:

{

  "id": "kemal\_sunal\_hayirdir",

  "tur": "template",

  "ad": "Hayırdır İnşallah",

  "kaynak": "Kemal Sunal",

  "gorsel\_tanim": "Kemal Sunal'ın gözlerini kısarak şüpheyle ve hafif tebessümle ileriye baktığı yakın plan sahne.",

  "durum": "Beklenmedik veya şüpheli bir teklif karşısında duyulan temkinli şaşkınlık ve güvensizlik.",

  "ornek\_durumlar": \[

    "Patron cuma 17:55'te 'müsaitsen odama gelir misin' yazdığında",

    "Yıllardır aramayan birinin 'kanka çok acil baksana' demesi"

  \],

  "uygun\_olmayan\_durumlar": \[

    "Gerçek ve trajik bir kaza haberi alındığında"

  \],

  "es\_anlam\_ve\_slang": \["hayırdır", "işkillenmek", "ayak yapmak", "dolap dönüyor"\],

  "kulturel\_bilgi": "Türk sinemasında kurnazlığa karşı uyanık olma refleksini temsil eden kült sahne.",

  "duygu": \["suphe", "saskinlik"\],

  "niyet": \["tepki\_gosterme", "gecistirme"\],

  "mekanizma": \["ironi", "beklenti\_gerceklik\_zitligi"\],

  "uyari": \[\],

  "annotator": \["a1"\],

  "reviewer": "a2",

  "sema\_versiyonu": "v2.0.0"

}