# ADR-0009: Tekil Annotator ve Eşik Tabanlı Asenkron Ekip Denetim Mimarisi

- **Durum:** Önerildi (Alternatif Mimari Tasarımı)
- **Tarih:** 2026-10-16
- **İlgili:** `docs/annotation.md`, `architecture.md`, `openapi.yaml`

## Bağlam
Veri kümesindeki tüm meme ve GIF'lerin 4 kişi tarafından aynı anda etiketlenmesi üslup tutarsızlığına, çakışmalara ve gereksiz efor kaybına yol açmaktadır. Ancak etiketleme tamamen tek bir kişiye bırakıldığında da ekip içi kalibrasyon, ortak vizyon ve kalite kontrol riske girmektedir.

Ayrıca annotator odaklanmış halde form doldururken arayüze anlık düşen canlı bildirimler ve yorumlar dikkat dağınıklığına yol açmaktadır.

## Karar

1. **Tekil Annotator, Şeffaf İzleme:**
   - Veri setindeki tüm meme/GIF'ler tek bir birincil annotator tarafından etiketlenir.
   - Ekibin diğer 3 üyesi sistemi salt-okunur (read-only) olarak dilediği zaman açıp inceler.
   - Panel üzerinde toplam meme sayısı, kaçının etiketlendiği ve kaçının kaldığı tüm ekip üyelerine canlı sayaçlarla gösterilir.

2. **Asenkron Geri Bildirim (Pull / Refresh Modeli):**
   - İnceleyen ekip üyeleri meme ve alan bazında yorum bırakabilir.
   - Canlı web-socket push bildirimleri yerine e-posta/inbox mantığı uygulanır: Annotator sayfayı yenilediğinde (refresh/re-fetch) veya sonraki meme'e geçtiğinde yeni yorumları ve düzeltme taleplerini çeker (pull eder).

3. **5 Üzerinden Ekip Oylaması ve Eşik Kuralı (Scoring & Thresholds):**
   - İzleyici ekip üyeleri tamamlanan her bir annotation için 1–5 arası puan verir.
   - **Ortalama Puan < 2.00:** Annotation doğrudan `reddedildi` durumuna geçer ve geçersiz sayılır.
   - **2.00 <= Ortalama Puan < 2.50:** Durum otomatik olarak `tekrar_gozden_gecirilmeli` yapılır; annotator ekibin yorumlarına göre kaydı revize etmek zorundadır.
   - **Ortalama Puan >= 2.50:** Kayıt geçerli kabul edilir ve inceleme kuyruğundan onay aşamasına geçer.

## Sonuçlar
- 4 kişinin aynı anda veri girip yorulması önlenir, tekil sorumlulukla homojen bir veri dili kurulur.
- Ekip ruhu ve ortak kalite eşiği 5 yıldızlı oylama ve katı eşik puanlarıyla korunur.
- Annotator form doldururken gereksiz canlı bildirimlerle bölünmez.
