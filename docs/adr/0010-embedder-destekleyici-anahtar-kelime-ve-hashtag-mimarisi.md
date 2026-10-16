# ADR-0010: Dense Embedder Destekleyici Anahtar Kelime ve Hashtag Mimarisi

- **Durum:** Önerildi (Alternatif Mimari Tasarımı)
- **Tarih:** 2026-10-16
- **İlgili:** `docs/annotation.md` §3.2, `architecture.md` §1-§4

## Bağlam
Sistem çalışma anında (runtime) generative LLM çalıştırmamakta; anlamsal eşleşmeyi Türkçe dense embedding modelleri (`ytu-ce-cosmos`, `bge-m3`) üzerinden latent uzay yakınsamasıyla sağlamaktadır. 

Meme'in soyut durumu paragraf olarak anlatıldığında, model bazen arama anındaki kısa argo terimleri, eş anlamlıları ve kestirme duygu patlamalarını merkezden uzak görebilmektedir (embedding dilution).

## Karar

1. **Dense Retrieval Uyumlu Etiketleme:**
   - Annotator, embedder'ın vektör uzayında nasıl çalıştığını bilerek etiketleme yapar. Soyut durum iskeleti somut nesnelerden arındırılır.
2. **Hashtag ve Anahtar Kelime Enjeksiyonu (`anahtar_kelimeler`):**
   - Her meme'in açıklamasının ardına embedder'ın yakalamasını kolaylaştıracak 3–8 adet normalize edilmiş anahtar kelime/hashtag eklenir.
   - Örnek: Ağlayan çantalı köpek meme'i için:
     `#uzgun #mutsuz #hayalkirikligi #daralma #okulstresi #tukenmislik`
3. **Vektör Sentezi Entegrasyonu:**
   - Vektör motoruna beslenen metin derlemesine bu etiketler doğrudan dahil edilir:
     `TEXT_FOR_V_CONTEXT = f"{durum}. Etiketler: {' '.join(anahtar_kelimeler)}"`

## Sonuçlar
- Kısa ve argo arama terimleri ("yıkıldım", "patladım") doğrudan eşleşen hashtag vektörlerine çekilir.
- Dil modellerinin latent uzayındaki komşuluk performansı artar, arama doğruluğu (Recall@k) yükselir.
