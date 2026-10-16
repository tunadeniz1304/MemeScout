# ADR-0011: Güvenli Veri Seti Standartları ve İstemci/Sunucu Seviyesinde İçerik Kalkanı (Guardrail)

- **Durum:** Önerildi (Alternatif Mimari Tasarımı)
- **Tarih:** 2026-10-16
- **İlgili:** `annotation-platform/openapi.yaml`, `docs/annotation.md`

## Bağlam
Projenin akademik standartlara uygun olması ve kurumsal/topluluk kullanımında sorun yaratmaması için veri setinin toksik unsurlardan temizlenmesi gerekmektedir. Veri setine siyasi, küfürlü, müstehcen, nefret söylemi veya ofansif içeriklerin girmesi kabul edilemez. Bu kontrolün yalnızca annotator'ın inisiyatifine bırakılması insan hatasına açıktır.

## Karar

1. **Katı İçerik Politikası:**
   - **Dataset Kısıtı:** Siyasi figür/olay içeren, ağır argo/küfür barındıran, müstehcen veya ofansif hiçbir meme/GIF platforma yüklenemez.
   - **Annotator Kısıtı:** Açıklama, durum ve anahtar kelime alanlarında siyasi kavramlar, küfür, argo hakaret ve ofansif ifadeler kullanılamaz.

2. **Otomatik Kayıt Engelleme Kalkanı (Guardrail Engine):**
   - Sisteme kapsamlı bir yasaklı kelime ve regex deseni kütüphanesi (`blacklist.json`) entegre edilir.
   - **Arayüz (Client-Side):** Annotator formu doldururken yasaklı bir kelime tespit edildiğinde alan kırmızıya döner, uyarı çıkar ve "Kaydet / Gönder" butonları devre dışı bırakılır.
   - **Backend (Server-Side Enforcement):** `PATCH /draft` veya `POST /submit` isteklerinde metin analiz edilir; ihlal varsa işlem veritabanına yazılmadan reddedilir:
     - HTTP Durum Kodu: `422 Unprocessable Entity`
     - Hata Kodu: `GUVENSIZ_ICERIK`
     - Detay: İhlal eden kelime ve bulunduğu alan bilgisi döndürülür.

## Sonuçlar
- Hatalı veya ofansif metinlerin taslak dahi olsa veritabanına kaydedilmesi teknik seviyede engellenir.
- Veri seti yayınlanabilir, temiz ve akademik bir çerçevede kalır.
