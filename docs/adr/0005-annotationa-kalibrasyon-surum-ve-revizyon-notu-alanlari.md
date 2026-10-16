# ADR-0005: Tekil Annotator Sürecinde `kalibrasyon`, `surum` ve `revizyon_notu` Alanları

- **Durum:** Kabul Edildi  
- **Tarih:** 2026-10-16  
- **İlgili:** `docs/annotation.md` §2, §3.3, §4, `annotation-platform/openapi.yaml`

---

## Bağlam

MemeScout projesinde veri tutarlılığını sağlamak ve üslup çatışmalarını engellemek amacıyla **tekil annotator (single-annotator curation)** modeli benimsenmiştir. Bu modelde tüm meme'ler tek bir kişi tarafından etiketlenir; ekibin diğer 3 üyesi ise yalnızca izleme (viewer), not/yorum bırakma, değerlendirme ve revizyon talep etme yetkilerine sahiptir.

Bu operasyonel işleyiş, veri modelinde şu teknik ihtiyaçları doğurmaktadır:

1. **Kalibrasyon Ayrımı:** İlk aşamada ekipçe yapılan ortak 10–15 meme'lik deneme/kalibrasyon kayıtları ile tekil annotator'ın girdiği ana gold veriyi şemada ayırt edecek bir bayrak gereklidir.  
2. **Sekme Çakışması ve Veri Kaybı Riski:** Tekil annotator aynı meme'i tarayıcıda yanlışlıkla birden fazla sekmede açtığında veya bağlantı dalgalanmasında otomatik taslak kayıtlarının birbiri üzerine yazılmasını (race condition) önleyecek bir iyimser kilitleme mekanizması şarttır.  
3. **Ekip İncelemesi ve Revizyon Geri Bildirimi:** Ekibin diğer 3 üyesi etiketleri izleyip kültürel arka plan, eksik argo/slang veya yetersiz tanımlar gördüğünde revizyon talep edebilmeli (`revizyon_gerekli`) ve annotator'a spesifik düzeltme talimatı iletebilmelidir.

---

## Karar

`Annotation` şemasına aşağıdaki üç alanın eklenmesi onaylanmıştır:

1. **`kalibrasyon` (bool, varsayılan `false`):**  
     
   - Projenin başında yapılan oryantasyon/kalibrasyon kayıtlarını işaretler.  
   - Arama motoruna aktarılacak nihai `gold.jsonl` kümesinden ve metrik analizlerinden bu bayrak ile izole edilir.

   

2. **`surum` (int, varsayılan `1`):**  
     
   - İyimser Kilitleme (Optimistic Locking) sayacıdır.  
   - Her `PATCH /annotations/{id}/draft` çağrısında 1 artırılır.  
   - İstemci elindeki sürüm numarasını gönderir; veritabanındaki sürümle eşleşmezse backend `409 SURUM_CAKISMASI` döner. Böylece tekil annotator'ın tarayıcı sekmeleri arasında veri kaybı önlenir.

   

3. **`revizyon_notu` (metin, nullable):**  
     
   - Etiketleri izleyen diğer ekip üyelerinin (reviewer/viewer) veya yöneticinin revizyon talebi gerekçesidir (`POST /annotations/{id}/request-revision`).  
   - Annotator kendi iş listesinde bu notu görerek doğrudan hedeflenen düzeltmeyi yapar.

---

## Sonuçlar

- **Tekil Sorumluluk Güvencesi:** Annotator veri girerken ekibin diğer üyeleri arayüze müdahale edemez; izleme ve denetleme süreçleri `revizyon_notu` ve yorumlar üzerinden asenkron yürütülür.  
- **Veri Bütünlüğü:** Sekme veya ağ kopmalarında taslakların üzerine yazılması engellenir.  
- **Şartname Uyumu:** `docs/annotation.md` §3.3 tablosu ve `openapi.yaml` dosyası bu alanlarla tam uyumlu hale getirilmiştir.