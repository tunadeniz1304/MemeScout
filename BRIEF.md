# BRIEF — MemeScout

## Problem
Sosyal medya / içerik ekipleri, gündelik kulnnaımda bir durum veya konuşma bağlamına uygun meme'i bulmak için dakikalarca arama yapıyor. Var olan araçlar Türkçe ironi, argo ve yerli meme kültürünü anlamıyor.

## Çözüm
Türkçe konuşmayı anlayan, neden o meme'i seçtiğini açıklayan agentic bir meme asistanı.

İki kullanım modu:
1. **Durum / Konuşma → Meme:** Kullanıcı bir durumu anlatır ya da bir konuşmayı (WhatsApp/Slack) yapıştırır, sistem uygun meme'leri getirir.
2. **Tarif → Meme:** Kullanıcı hatırladığı bir meme'i tarif eder, sistem onu bulur.

## Farklılaştırıcılar
1. **Türkçe + Türk meme kültürü:** Yerli template'ler (Kemal Sunal, Recep İvedik vb.) ve Türkçe argo/deyim/ironi anlama.
2. **Bağlam anlayan agent:**
   - Konuşma bağlamından "en iyi cevap ne olur"u çıkarma
   - Her sonuç için "neden bu meme" açıklaması
   - Refine döngüsü: "daha alaycı olsun", "daha az kaba" gibi isteklerle sorguyu yeniden yazıp tekrar arama
3. **İçerik uyarı etiketi:** Politik, kaba veya hassas içerik taşıyan meme'lere uyarı label'ı (filtreleme yok, sadece işaretleme).
4. **Değerlendirme:** Düz semantic search ile agentic sistemin karşılaştırılması.

## Hedef Kullanıcı
Şirket ve ajansların sosyal medya / içerik ekipleri.
Şahısların gündelik ve keyfi kullanımı.

## Mimari
- **Router Agent:** Girdi durum/konuşma mı, meme tarifi mi olduğunu belirler.
- **Context Agent:** Konuşmadan ya da durumdan duygu, ton ve niyeti çıkarıp arama sorgusuna çevirir.
- **Retrieval Agent:** Vektör DB'de hybrid arama yapar (VLM'in görsel tarifi + anahtar kelimeler + "ne zaman kullanılır" metni) ve re-rank eder.
- **Refine döngüsü:** Sonuç zayıfsa ya da kullanıcı geri bildirim verirse sorguyu yeniden yazıp tekrar arar.
- **Explain + Label adımı:** Her sonuca "neden bu meme" açıklaması ve gerekirse içerik uyarı etiketi ekler.

## Teknoloji
- Agent'lar: Python (LangGraph veya benzeri)
- LLM / VLM: API tabanlı (Türkçe performansı iyi bir model)
- Embedding + Vector DB: Çok dilli text embedding, Chroma veya Qdrant (CLIP aramada kullanılmaz, yalnızca veri toplarken kopya tespiti için)
- ReRanker
- Frontend: Serbest (Streamlit veya React)

## Veri
- Birkaç yüz(belki bin) Türk meme template'i (elle toplanacak) + popüler uluslararası template'ler (Imgflip, MemeMatch dataset)
- Her template için insanın yazdığı Türkçe kullanım bağlamı, duygu/niyet etiketleri ve hassasiyet (uyarı) bilgisi. Görsel tarifin taslağını VLM üretir, insan düzeltir.

## Değerlendirme
- 50–100 Türkçe durum/konuşma için elle hazırlanmış "kabul edilebilir meme'ler" listesi
- Baseline (düz semantic search) ile agentic sistemin recall@5 karşılaştırması

## Backlog (opsiyonel)
- Caption üretip görselin üstüne basarak hazır meme çıkarma (Pillow)

## Kapsam Dışı
- Sıfırdan görsel üretimi
- Video / GIF meme'ler
- Gerçek sosyal medya hesabına paylaşım
- İçeriği otomatik engelleme (yalnızca uyarı etiketi)

## Ekip
4 kişi. Önerilen iş bölümü: veri toplama + etiketleme, agent/RAG backend, frontend, evaluation + demo/rapor.(Toplu)

## Başarı Ölçütü
- Her iki modda Türkçe sorgulara makul sonuç dönen çalışan demo
- Agentic sistemin baseline'a göre recall@5'te ölçülebilir iyileşme göstermesi
