# MemeScout — Annotation Platformu

> Durum: Taslak. İçerik şemasının anlamı için [architecture.md](architecture.md) dokümanına bakın. Bu doküman platformun hangi verileri tutacağını, etiketleme sürecini ve platformdan beklenen özellikleri tanımlar.
>
> Frontend ile backend arasındaki istek ve cevapların tek doğru kaynağı [openapi.yaml](../annotation-platform/openapi.yaml) dosyasıdır ([ADR-0001](adr/0001-api-contract-tek-kaynak.md)). Form doğrulama kuralları backend'den `GET /schema/annotation` ile gelir. Bir değişiklik gerekirse önce sözleşme PR ile güncellenir, sonra kod.

## 1. Amaç ve Kapsam

- ~300 meme, 4 kişilik ekip tarafından elle etiketlenecek. Anlam alanlarını insan yazar; görsel tarifin taslağını VLM üretir, annotator düzeltir.
- Platformun çıktısı iki şeydir:
  1. Her meme için tek, kesinleşmiş bir kayıt (**gold**). Arama sistemi bunu kullanır.
  2. Her etiketleyicinin ham etiketleri. Etiketleyiciler arası uyum analizi bunlarla yapılır.
- Değerlendirmede kullanılacak test sorguları da bu platformda yazılır ve takip edilir.

## 2. Roller

| Rol | Yetki |
| --- | --- |
| **Annotator** | Kendisine atanan meme'leri etiketler, yorum ve işaret bırakır |
| **Reviewer** | Çift etiketlenen meme'lerde anlaşmazlıkları çözer, tek etiketlenen meme'lere ikinci bakış yapar, gold kaydı onaylar |
| **Admin** | Meme yükler, atama yapar, etiket listelerini yönetir, dışa aktarım alır |

4 kişilik ekipte herkes annotator'dır. Reviewer rolü dönüşümlü verilir: bir meme'in reviewer'ı, o meme'i etiketleyen kişilerden biri olamaz.

## 3. Veri Modeli

```
Meme 1───* Annotation *───1 Kullanıcı
 │            │
 │            └── versiyonlar (revizyon geçmişi)
 ├──1 GoldKayıt
 ├──* Yorum / İşaret
 └──* TestSorgusu (doğru cevap olarak)

EtiketListesi (versiyonlu)
DenetimKaydı (kim, ne zaman, neyi değiştirdi)
```

### 3.1 Meme (görsel bilgisi)

Bu alanların hepsini platform yükleme sırasında otomatik doldurur. Kullanıcı sadece görseli seçer, başka bir şey girmez.

| Alan | Tip | Nasıl dolar |
| --- | --- | --- |
| `id` | string | Otomatik üretilir (dosya adından ya da sıra numarasından) |
| `gorsel_yolu` | string | Dosyanın depolamaya kaydedildiği yol |
| `sha256` | string | Dosyadan hesaplanır. Aynı dosyanın iki kez yüklenmesini engeller |
| `yukleyen` | kullanıcı | Giriş yapmış kullanıcı |
| `yuklenme_zamani` | zaman damgası | Yükleme anı |
| `vlm_taslak` | metin | Yükleme sırasında VLM'e ürettirilir: görselde ne olduğunun yorumsuz tarifi. Sonradan değiştirilmez. Annotation'daki `vlm_aciklama` alanını önceden doldurmak ve VLM'in ne kadar düzeltildiğini görmek için saklanır |

Elimizdeki mevcut ~300 meme platforma toplu olarak aktarılır. Bu aktarımda da alanlar aynı şekilde otomatik dolar. `yukleyen` alanına aktarımı başlatan kişi yazılır.

Meme'i kimlerin etiketlediği `Annotation` kayıtlarında tutulur (§3.3). Meme listesinde her meme'in yanında annotator'ları bu kayıtlardan türetilerek gösterilir.

### 3.2 Annotation (içerik etiketleri)

Her meme–annotator çifti için ayrı bir kayıt tutulur. Alanların anlamı [architecture.md §3](architecture.md#3-annotation-şeması) bölümündedir. Platformun uygulayacağı doğrulama kuralları:

| Alan | Tip | Zorunlu | Doğrulama |
| --- | --- | --- | --- |
| `tur` | enum | ✓ | `template` veya `hazir_meme` |
| `ad` | string | ✓ | En fazla 60 karakter |
| `kaynak` | string | | Eser, karakter, sahne. En fazla 100 karakter |
| `vlm_aciklama` | metin | ✓ | VLM taslağıyla (`vlm_taslak`) dolu gelir, annotator düzeltir. Yalnızca görselde görünenler: kişi, yüz ifadesi, nesne, sahne, yazı. 20–250 karakter |
| `durum` | metin | ✓ | 20–200 karakter. Somut varlık değil, soyut iskelet |
| `ornek_durumlar` | metin listesi | ✓ | 3–5 adet, birbirinin tekrarı olmamalı. Her biri en fazla 150 karakter |
| `uygun_olmayan_durumlar` | metin listesi | ✓ | 1–2 adet. Her biri en fazla 150 karakter |
| `kulturel_bilgi` | metin | ✓ | Gereken arka plan ve neden komik olduğu. En fazla 500 karakter |
| `anahtar_kelimeler` | metin listesi | ✓ | 3–8 adet, her biri en fazla 40 karakter. Düz Türkçe ve Türkçe karakterli; hashtag ve bitişik yazım yok |
| `duygu` | etiket listesi | ✓ | 1–3 etiket, sabit listeden |
| `niyet` | etiket listesi | ✓ | 1–3 etiket, sabit listeden |
| `mekanizma` | etiket listesi | ✓ | 1–3 etiket, sabit listeden |
| `uyari` | etiket listesi | ✓ | Cevaplanması zorunlu ([ADR-0004](adr/0004-uyari-null-ve-bos-liste.md)): `null` henüz cevaplanmadı demektir ve gönderilemez; `[]` bilinçli "uyarı yok" onayıdır |
| `notlar` | metin | | Serbest not. En fazla 500 karakter |

Üst sınırlar başlangıç değeridir; kalibrasyon turundan sonra gözden geçirilir.

### 3.3 Annotation (süreç bilgisi)

İçerik etiketleriyle birlikte otomatik ya da yarı otomatik tutulur.

| Alan | Tip | Açıklama |
| --- | --- | --- |
| `annotator` | kullanıcı | Etiketleyen kişi |
| `durum_kodu` | enum | Bkz. §4.2 |
| `atanma_zamani`, `baslama_zamani`, `gonderme_zamani` | zaman damgası | |
| `harcanan_sure_sn` | int | Aktif süre. Emek tahmini ve rapor için |
| `tanidiklik` | 1–5 | 1: hiç görmedim, 2: gördüm ama ne anlattığını bilmiyorum, 3: anlamını biliyorum ama kullanmam, 4: biliyorum ve ara sıra kullanırım, 5: çok iyi biliyorum, kaynağını ve kullanımlarını tanıyorum |
| `alan_guveni` | alan → 1–3 | Annotator'ın emin olmadığı alanları işaretlemesi için |
| `atlandi` | bool + gerekçe | "Bu meme'i tanımıyorum" ya da "uygun değil" gibi |
| `sema_versiyonu` | string | Hangi şema versiyonuyla etiketlendi |
| `etiket_listesi_versiyonu` | string | Hangi etiket listesi versiyonuyla etiketlendi |
| `cift_etiket` | bool | Uyum ölçümü için çift etiketlenen alt kümede mi |
| `kalibrasyon` | bool | Kalibrasyon turuna ait annotation. Uyum hesaplarına katılmaz ([ADR-0005](adr/0005-annotation-ek-alanlari.md)) |
| `surum` | int | Her taslak kaydında artar. İstemci son bildiği sürümü gönderir; eşleşmezse backend `409 SURUM_CAKISMASI` döner. Aynı annotation iki sekmede açıksa veri kaybını önler |
| `revizyon_notu` | metin | Reviewer ya da admin revizyon isterken yazdığı not; annotator'ın kuyruğunda görünür |

`tanidiklik` ve `alan_guveni` önemli: Kültürel bağlamı bilmeyen birinin etiketi, bilen birininkiyle aynı ağırlıkta olmamalı. Tanıdıklık skoru 1 veya 2 olan annotation gönderilemez; atlanır ve başka birine yeniden atanır.

### 3.4 Gold kayıt

Her meme için bir tane. Arama sisteminin kullandığı kayıt budur.

| Alan | Açıklama |
| --- | --- |
| İçerik alanları | §3.2 ile aynı yapı |
| `kaynak_annotationlar` | Gold kaydın hangi annotation'lardan türetildiği |
| `annotator` | Kaynak annotation'ların sahipleri, takma adla liste (ör. `["a1", "a3"]`). Tek etiketli meme'de tek elemanlı liste ([ADR-0006](adr/0006-gold-annotator-liste.md)) |
| `reviewer` | Onaylayan kişi. Tek etiketli meme'lerde ikinci bakışı yapan kişidir ([ADR-0009](adr/0009-tek-etiketli-memelerde-ikinci-bakis.md)) |
| `sema_versiyonu`, `etiket_listesi_versiyonu` | Kaydın hangi şema ve etiket listesi versiyonuyla oluşturulduğu |
| `cozum_notu` | Anlaşmazlık nasıl çözüldü |
| `onay_zamani` | |

Tek etiketlenen meme'lerde gold kayıt o annotation'dan oluşur ve reviewer'ın ikinci bakışıyla kesinleşir.

### 3.5 Yorum ve işaret

Annotator'ların ekipçe tartışmak istediği durumlar için. Örnek: "Bu meme politik mi sayılır?", "Bu iki meme aynı template mi?"

| Alan | Açıklama |
| --- | --- |
| `meme`, `alan` | Hangi meme, hangi alan (opsiyonel) |
| `yazan`, `zaman`, `metin` | |
| `tur` | soru, kılavuza ekleme önerisi, kopya şüphesi, hata |
| `cozuldu` | bool |

### 3.6 Etiket listesi

Duygu, niyet, mekanizma ve uyarı listeleri platformda **versiyonlu** tutulur.

| Alan | Açıklama |
| --- | --- |
| `alan` | duygu, niyet, mekanizma, uyari |
| `etiket` | Sistem adı: küçük harf, Türkçe karaktersiz, boşluk yerine alt çizgi (ör. `bikkinlik`, `tepki_gosterme`; [ADR-0008](adr/0008-etiket-sistem-adlari.md)) |
| `gorunen_ad` | ör. "Bıkkınlık" |
| `tanim` | Kılavuzdaki kısa tanım |
| `ornekler` | 1–2 örnek meme |
| `versiyon`, `eklenme_tarihi`, `aktif` | |

Bir etiket eklendiğinde ya da çıkarıldığında, eski versiyonla etiketlenmiş kayıtlar "yeniden kontrol" listesine düşer.

### 3.7 Test sorgusu

Değerlendirme seti (~100 sorgu) de platformda tutulur.

| Alan | Açıklama |
| --- | --- |
| `id`, `metin` | Durum ya da konuşma metni |
| `mod` | `durum` veya `tarif` |
| `dogru_memeler` | Bir veya birden fazla meme |
| `yazan` | Sorguyu yazan kişi |
| `zaman` | |
| `parafraz_grubu` | Opsiyonel. Aynı durumun farklı yazımları aynı grup kimliğini taşır ve aynı `dogru_memeler` listesini paylaşır ([architecture.md §6](architecture.md#6-değerlendirme), parafraz alt kümesi) |

**Sızıntı kuralı ([ADR-0002](adr/0002-sizinti-kurali-reviewer-dahil.md)):** Test sorgusunu yazan kişi, doğru cevap olarak gösterdiği meme'lerin gold kaydına katkı veren hiç kimse olamaz: kaynak annotation'ların sahipleri ve reviewer. Platform ihlalde `422 SIZINTI` döner ve sorunlu meme'leri listeler. Aynı `parafraz_grubu`'ndaki varyantlar için de kural aynıdır. Mümkünse sorguları ekip dışından biri yazar; bu, kuraldan daha güçlü bir korumadır.

### 3.8 Denetim kaydı

Her değişiklik için: kim, ne zaman, hangi kayıt, hangi alan, eski değer, yeni değer. Revizyon geçmişi ve "kim neyi değiştirdi" soruları bununla cevaplanır.

## 4. Etiketleme Süreci

### 4.1 Aşamalar

1. **Kılavuz:** Etiket tanımları ve örneklerle etiketleme kılavuzu yazılır.
2. **Kalibrasyon turu:** 4 kişinin hepsi aynı 10–15 meme'i etiketler. Sonuçlar birlikte tartışılır ve kılavuz güncellenir. Bu turun etiketleri `kalibrasyon` ile işaretlenir ve uyum ölçümüne katılmaz.
3. **Ana etiketleme:** 300 meme 4 kişiye bölünür, kişi başı ~75 meme.
4. **Çift etiketleme:** Meme'lerin ~%20'si (~60 meme) ikinci bir kişiye de atanır. 4 kişiden 6 farklı ikili çıkar, her ikiliye ~10 meme düşer. Böylece uyum, kişiden bağımsız ölçülür. İlk yarısı (~30 meme) bittiğinde ara uyum ölçümü yapılır (§6).
5. **Uyum ölçümü ve çözüm:** Anlaşmazlıkları üçüncü bir kişi (reviewer) çözer.
6. **İkinci bakış:** Tek etiketlenen meme'leri, onları etiketlemeyen bir reviewer hızlıca kontrol eder; onaylar ya da `revizyon_notu` ile geri gönderir ([ADR-0009](adr/0009-tek-etiketli-memelerde-ikinci-bakis.md)). Bu kontrol uyum ölçümüne katılmaz.
7. **Test seti:** Sızıntı kuralına uyularak ~100 test sorgusu yazılır. Bunlardan 20'si için 2'şer parafraz varyantı eklenir (§3.7, `parafraz_grubu`).
8. **Dışa aktarım:** Gold kayıtlar arama sistemine aktarılır.

### 4.2 Annotation durumları

```
atanmadi → atandi → devam_ediyor → gonderildi ─┬─► onaylandi
                         ▲                     │
                         └── revizyon_gerekli ◄┘
                    atlandi (tanımıyorum / uygun değil)
```

Revizyonu reviewer ya da admin `revizyon_notu` ile ister (`gonderildi → revizyon_gerekli`). Atlanan ya da tanıdıklığı düşük annotation'ı admin başka birine yeniden atar ([ADR-0007](adr/0007-ek-api-islemleri.md)).

### 4.3 Kör etiketleme

Çift etiketlenen meme'lerde iki kişi de göndermeden önce birbirinin etiketini göremez. Aksi halde ikinci kişi ilkinden etkilenir ve uyum olduğundan yüksek çıkar.

Kural yorumları da kapsar ([ADR-0003](adr/0003-kor-etiketlemede-yorumlar-gizli.md)): iki annotation da `gonderildi` olana kadar bir annotator, diğerinin o meme'e bıraktığı yorumları göremez. Admin ve reviewer bütün yorumları görür. Genel sorular meme'e değil ekip kanalına sorulur ya da kılavuza ekleme önerisi olarak yazılır. VLM taslağı iki kişiye de aynı gelir; diğer annotator'ın çıktısı olmadığı için kör etiketlemeyi bozmaz.

## 5. Platformdan Beklenen Özellikler

**Etiketleme ekranı**
- Görsel büyük ve yakınlaştırılabilir, form yanında
- Görsel tarif alanı VLM taslağıyla dolu gelir; görsel tarif ile anlam alanları formda ayrı bloklarda durur
- Etiket seçicilerinde her etiketin üzerine gelince kılavuzdaki tanımı göster
- Otomatik taslak kaydı (sayfa kapanırsa iş kaybolmasın)
- "Tanımıyorum / atla" butonu
- Alan bazında "emin değilim" işareti
- Klavye kısayolları (sonraki meme, kaydet, gönder)
- Doğrulama kuralları ihlal edilirse gönderme engellenir ve sebebi gösterilir
- Göndermeden önce eksikleri gösteren "Doğrula" butonu
- Uyarı etiketlerinin yanında ayrı bir "Uyarı yok" onay kutusu

**Yönetim ve takip**
- İlerleme panosu: kişi başı tamamlanan, kalan, atlanan, ortalama süre
- Uyum panosu: alan bazında uyum skorları ve en çok anlaşmazlık çıkan etiketler
- Anlaşmazlık ekranı: iki annotation yan yana, reviewer seçer ya da birleştirir
- İkinci bakış kuyruğu: reviewer'a düşen tek etiketli kayıtlar; onayla ya da notla geri gönder
- Kopya uyarısı: yüklenen dosyanın `sha256` değeri mevcut bir meme'le aynıysa yüklemeyi engelle
- Otomatik dağıtım: atanmamış meme'leri annotator'lara eşit böler, ~%20'sini ikinci bir kişiye de atar ve ikinci atamaları ikililere dengeli dağıtır. Önce plan görülebilir. İlk sürümde olmayabilir
- Yeniden atama: atlanan ya da tanıdıklığı düşük annotation başka birine atanır
- Revizyon isteme: reviewer ya da admin, gönderilmiş bir annotation için notla revizyon ister. İlk sürümde olmayabilir

**Dışa aktarım**
- `gold.jsonl`: Meme başına bir satır gold kayıt, architecture.md şemasında. `annotator` ve `uyari` her zaman listedir (`null` olmaz)
- `annotations_raw.jsonl`: Tüm ham annotation'lar ve süreç bilgisi (uyum analizi için)
- `test_set.jsonl`: Test sorguları
- Dışa aktarımda annotator kimlikleri takma adla (`a1`–`a4`) yazılır

## 6. Uyum Ölçümü

| Alan türü | Metrik |
| --- | --- |
| Tek seçimli alanlar (`tur`) | Cohen's kappa |
| Çok etiketli alanlar (`duygu`, `niyet`, `mekanizma`, `uyari`) | Krippendorff's alpha (MASI mesafesiyle) veya etiket bazında kappa |
| Serbest metin (`durum`, `kulturel_bilgi`, `vlm_aciklama`, `anahtar_kelimeler`) | Sayısal ölçüm yerine reviewer'ın "aynı anlamı taşıyor mu" değerlendirmesi |

Bir etikette uyum düşük çıkarsa (kabaca kappa < 0,4), o etiketin tanımı kılavuzda netleştirilir ya da etiket başka bir etiketle birleştirilir. Ara ölçümde (§4.1) düşük çıkan alanlar, ikinci bakışta tek etiketli meme'lerde özellikle kontrol edilir. Kılavuz güncellemesinden sonra da düşük kalırsa kalan meme'lerde çift etiketleme oranı artırılır (ör. %20'den %40'a).
