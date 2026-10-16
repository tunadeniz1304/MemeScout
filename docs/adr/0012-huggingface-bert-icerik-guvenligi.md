# ADR-0013: Hugging Face BERT Tabanlı Yerel İçerik Güvenliği ve Moderasyon Mimarisi

- **Durum:** Önerildi  
- **Tarih:** 2026-10-16  
- **İlgili:** `docs/annotation.md` §3.2, §5, `architecture.md` §2, `annotation-platform/openapi.yaml`, `docs/adr/0012-icerik-guvenligi-ve-otomatik-kayit-onleme-guardrail.md`

---

## 1\. Bağlam

MemeScout projesinde hem arama motoruna iletilen kullanıcı sorgularının (`/search`) hem de etiketleme platformunda oluşturulan içeriklerin (`durum`, `gorsel_tanim`, `es_anlam_ve_slang`) siyaset, küfür, müstehcenlik ve ofansif nefret söyleminden arındırılması gerekmektedir.

Geleneksel kelime bazlı kara listeler (string matching / regex) harf manipülasyonlarını, örtülü hakaretleri ve bağlamsal toksisiteyi yakalamakta yetersiz kalmaktadır. Harici bulut API'leri (OpenAI Moderation, Google Perspective vb.) ise ağ gecikmesi, harici servis bağımlılığı, kota sınırları ve veri gizliliği riskleri barındırmaktadır.

Bu doğrultuda, platformun içerik güvenliği denetiminin harici hiçbir bulut servisi veya manuel kural listesi kullanılmaksızın, **doğrudan Hugging Face ekosistemindeki açık kaynaklı Türkçe transformer modelleri** üzerinden yerel olarak yürütülmesi ihtiyacı doğmuştur.

---

## 2\. Karar

Tüm metin moderasyonunun Hugging Face üzerindeki önceden eğitilmiş Türkçe dil modelleri (`transformers` kütüphanesi) ile yerel ortamda yürütülmesine karar verilmiştir.

\[Kullanıcı Sorgusu / Annotator İçeriği\]

                     │

                     ▼

  ┌────────────────────────────────────────────────────────┐

  │ Hugging Face BERT Türkçe Moderasyon Hattı (Pipeline)  │

  │ Model: \`emrecan/bert-base-turkish-cased-offensive\`    │

  │        (veya \`savasy/bert-turkish-text-classification\`)│

  │ Motor: Yerel ONNX / PyTorch Inference                 │

  └──────────────────────────┬─────────────────────────────┘

                             │

             ┌───────────────┴───────────────┐

          Toksik / Ofansif                Temiz

       (Güven Skoru \>= 0.80)       (Güven Skoru \< 0.80)

             │                               │

             ▼                               ▼

    \[422 GUVENSIZ\_ICERIK\]            \[İşleme İzin Ver\]

    (İşlem Durdurulur)             (Arama / Kayıt Tamamlanır)

### 2.1 Model Seçimi ve Yerel Yürütme

- Moderasyon hattında Hugging Face Hub üzerinde yer alan açık kaynaklı Türkçe ofansif sınıflandırma modeli kullanılacaktır:  
  - **Birincil Model:** `emrecan/bert-base-turkish-cased-offensive`  
  - **Alternatif/Yedek Model:** `savasy/bert-turkish-text-classification`  
- Model ağırlıkları yerel önbelleğe (`~/.cache/huggingface`) indirilir ve sunucu ayağa kalkarken belleğe yüklenir.  
- Çıkarım (inference) performansı ve CPU verimliliği için model yerel olarak ONNX Runtime formatına optimize edilerek çalıştırılır.

### 2.2 Denetim Noktaları ve Eşik Değeri (Thresholding)

1. **Arama Motoru (`GET /search`):** Kullanıcı sorgusu BERT sınıflandırıcısından geçirilir. Modelin ofansiflik güven skoru \$\\ge 0.80\$ ise arama işletilmez; `422 GUVENSIZ_ICERIK` döner.  
2. **Etiketleme Platformu (`POST /submit`):** Annotator'ın girdiği `durum`, `gorsel_tanim` ve `es_anlam_ve_slang` alanları birleştirilerek modele beslenir. Ofansiflik skoru eşiği aşıyorsa gönderim engellenir.

---

## 3\. OpenAPI ve Hata Sözleşmesi Uyumu

Model tarafından zararlı içerik tespit edildiğinde ADR-0001 sözleşmesine uygun standart hata nesnesi üretilir:

{

  "hata": {

    "kod": "GUVENSIZ\_ICERIK",

    "mesaj": "Metin, Hugging Face BERT içerik denetim modeli tarafından zararlı veya uygunsuz olarak değerlendirildi.",

    "alanlar": \[

      {

        "alan": "durum",

        "kural": "guvensiz\_icerik",

        "mesaj": "Bağlamsal hakaret, küfür veya uygunsuz içerik tespit edildi."

      }

    \],

    "detay": {

      "model": "emrecan/bert-base-turkish-cased-offensive",

      "ofansiflik\_skoru": 0.92

    }

  }

}

---

## 4\. Sonuçlar

### Pozitif

- **Bağlamsal Anlama Gücü:** Kelime listelerinin yakalayamadığı örtülü hakaretler, imalar ve harf değiştirme hileleri BERT modelinin dikkat (attention) mekanizmasıyla yakalanır.  
- **Sıfır Bulut Bağımlılığı ve Maliyet:** OpenAI veya Google gibi harici sağlayıcılara bağımlılık, ağ gecikmesi ve faturalandırma ortadan kalkar.  
- **Akademik Standart:** Proje sunumunda ve raporunda kural tabanlı basit if-else kontrolleri yerine açık kaynaklı bir derin öğrenme modelinin entegre edildiği net bir şekilde sergilenir.

### Negatif / Kısıtlar

- **Bellek Tüketimi:** BERT modelinin bellekte tutulması \~400–500 MB RAM alanı gerektirir.  
- **Gecikme:** CPU üzerinde her sınıflandırma işlemi ortalama 15–35 ms sürer (ONNX optimizasyonu ile bu süre 10 ms bandına indirilecektir).