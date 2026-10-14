# MemeScout — Annotation Platformu

> Durum: Taslak. İçerik şemasının anlamı için [architecture.md](architecture.md) dokümanına bakın. Bu doküman platformun hangi verileri tutacağını, etiketleme sürecini ve platformdan beklenen özellikleri tanımlar.

## 1. Amaç ve Kapsam

- ~300 meme, 4 kişilik ekip tarafından elle etiketlenecek.
- Platformun çıktısı iki şeydir:
  1. Her meme için tek, kesinleşmiş bir kayıt (**gold**). Arama sistemi bunu kullanır.
  2. Her etiketleyicinin ham etiketleri. Etiketleyiciler arası uyum analizi bunlarla yapılır.
- Değerlendirmede kullanılacak test sorguları da bu platformda yazılır ve takip edilir.

## 2. Roller

| Rol | Yetki |
| --- | --- |
| **Annotator** | Kendisine atanan meme'leri etiketler, yorum ve işaret bırakır |
| **Reviewer** | Çift etiketlenen meme'lerde anlaşmazlıkları çözer, gold kaydı onaylar |
| **Admin** | Meme yükler, atama yapar, etiket listelerini yönetir, dışa aktarım alır |

4 kişilik ekipte herkes annotator'dır. Reviewer rolü dönüşümlü verilir: bir meme'in reviewer'ı, o meme'i etiketleyen iki kişiden biri olamaz.

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

Elimizdeki mevcut ~300 meme platforma toplu olarak aktarılır. Bu aktarımda da alanlar aynı şekilde otomatik dolar. `yukleyen` alanına aktarımı başlatan kişi yazılır.

Meme'i kimlerin etiketlediği `Annotation` kayıtlarında tutulur (§3.3). Meme listesinde her meme'in yanında annotator'ları bu kayıtlardan türetilerek gösterilir.

### 3.2 Annotation (içerik etiketleri)

Her meme–annotator çifti için ayrı bir kayıt tutulur. Alanların anlamı [architecture.md §3](architecture.md#3-annotation-şeması) bölümündedir. Platformun uygulayacağı doğrulama kuralları:

| Alan | Tip | Zorunlu | Doğrulama |
| --- | --- | --- | --- |
| `tur` | enum | ✓ | `template` veya `hazir_meme` |
| `ad` | string | ✓ | |
| `kaynak` | string | | Eser, karakter, sahne |
| `durum` | metin | ✓ | En az 20 karakter. Somut varlık değil, soyut iskelet |
| `ornek_durumlar` | metin listesi | ✓ | 3–5 adet, birbirinin tekrarı olmamalı |
| `uygun_olmayan_durumlar` | metin listesi | ✓ | 1–2 adet |
| `kulturel_bilgi` | metin | ✓ | Gereken arka plan ve neden komik olduğu |
| `duygu` | etiket listesi | ✓ | 1–3 etiket, sabit listeden |
| `niyet` | etiket listesi | ✓ | 1–3 etiket, sabit listeden |
| `mekanizma` | etiket listesi | ✓ | 1–3 etiket, sabit listeden |
| `uyari` | etiket listesi | | Boş olabilir. Boş bırakmak bilinçli bir seçimdir ("uyarı yok" onayı) |
| `notlar` | metin | | Serbest not |

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

`tanidiklik` ve `alan_guveni` önemli: Kültürel bağlamı bilmeyen birinin etiketi, bilen birininkiyle aynı ağırlıkta olmamalı. Tanıdıklık skoru 1 veya 2 olan meme başka birine yeniden atanır.

### 3.4 Gold kayıt

Her meme için bir tane. Arama sisteminin kullandığı kayıt budur.

| Alan | Açıklama |
| --- | --- |
| İçerik alanları | §3.2 ile aynı yapı |
| `kaynak_annotationlar` | Gold kaydın hangi annotation'lardan türetildiği |
| `reviewer` | Onaylayan kişi (çift etiketli meme'lerde) |
| `cozum_notu` | Anlaşmazlık nasıl çözüldü |
| `onay_zamani` | |

Tek etiketlenen meme'lerde gold kayıt doğrudan o annotation'dan oluşur.

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
| `etiket` | ör. `bikkinlik` |
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

**Sızıntı kuralı:** Bir kişi, `ornek_durumlar` alanını kendisinin yazdığı meme'leri doğru cevap olarak gösteren test sorgusu yazamaz. Platform bunu `yazan` ve `annotator` alanlarını karşılaştırarak engeller.

### 3.8 Denetim kaydı

Her değişiklik için: kim, ne zaman, hangi kayıt, hangi alan, eski değer, yeni değer. Revizyon geçmişi ve "kim neyi değiştirdi" soruları bununla cevaplanır.

## 4. Etiketleme Süreci

### 4.1 Aşamalar

1. **Kılavuz:** Etiket tanımları ve örneklerle etiketleme kılavuzu yazılır.
2. **Kalibrasyon turu:** 4 kişinin hepsi aynı 10–15 meme'i etiketler. Sonuçlar birlikte tartışılır ve kılavuz güncellenir. Bu turun etiketleri uyum ölçümüne katılmaz.
3. **Ana etiketleme:** 300 meme 4 kişiye bölünür, kişi başı ~75 meme.
4. **Çift etiketleme:** Meme'lerin ~%20'si (~60 meme) ikinci bir kişiye de atanır. 4 kişiden 6 farklı ikili çıkar, her ikiliye ~10 meme düşer. Böylece uyum, kişiden bağımsız ölçülür.
5. **Uyum ölçümü ve çözüm:** Anlaşmazlıkları üçüncü bir kişi (reviewer) çözer.
6. **Test seti:** Sızıntı kuralına uyularak ~100 test sorgusu yazılır.
7. **Dışa aktarım:** Gold kayıtlar arama sistemine aktarılır.

### 4.2 Annotation durumları

```
atanmadi → atandi → devam_ediyor → gonderildi ─┬─► onaylandi
                         ▲                     │
                         └── revizyon_gerekli ◄┘
                    atlandi (tanımıyorum / uygun değil)
```

### 4.3 Kör etiketleme

Çift etiketlenen meme'lerde iki kişi de göndermeden önce birbirinin etiketini göremez. Aksi halde ikinci kişi ilkinden etkilenir ve uyum olduğundan yüksek çıkar.

## 5. Platformdan Beklenen Özellikler

**Etiketleme ekranı**
- Görsel büyük ve yakınlaştırılabilir, form yanında
- Etiket seçicilerinde her etiketin üzerine gelince kılavuzdaki tanımı göster
- Otomatik taslak kaydı (sayfa kapanırsa iş kaybolmasın)
- "Tanımıyorum / atla" butonu
- Alan bazında "emin değilim" işareti
- Klavye kısayolları (sonraki meme, kaydet, gönder)
- Doğrulama kuralları ihlal edilirse gönderme engellenir ve sebebi gösterilir

**Yönetim ve takip**
- İlerleme panosu: kişi başı tamamlanan, kalan, atlanan, ortalama süre
- Uyum panosu: alan bazında uyum skorları ve en çok anlaşmazlık çıkan etiketler
- Anlaşmazlık ekranı: iki annotation yan yana, reviewer seçer ya da birleştirir
- Kopya uyarısı: yüklenen dosyanın `sha256` değeri mevcut bir meme'le aynıysa yüklemeyi engelle

**Dışa aktarım**
- `gold.jsonl`: Meme başına bir satır gold kayıt, architecture.md şemasında
- `annotations_raw.jsonl`: Tüm ham annotation'lar ve süreç bilgisi (uyum analizi için)
- `test_set.jsonl`: Test sorguları
- Dışa aktarımda annotator kimlikleri takma adla (`a1`–`a4`) yazılır

## 6. Uyum Ölçümü

| Alan türü | Metrik |
| --- | --- |
| Tek seçimli alanlar (`tur`) | Cohen's kappa |
| Çok etiketli alanlar (`duygu`, `niyet`, `mekanizma`, `uyari`) | Krippendorff's alpha (MASI mesafesiyle) veya etiket bazında kappa |
| Serbest metin (`durum`, `kulturel_bilgi`) | Sayısal ölçüm yerine reviewer'ın "aynı anlamı taşıyor mu" değerlendirmesi |

Bir etikette uyum düşük çıkarsa (kabaca kappa < 0,4), o etiketin tanımı kılavuzda netleştirilir ya da etiket başka bir etiketle birleştirilir.
