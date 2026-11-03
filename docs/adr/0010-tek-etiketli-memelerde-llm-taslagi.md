# ADR-0010: Tek etiketli meme'lerde LLM taslağı

- **Durum:** Kabul edildi
- **Tarih:** 2026-11-03
- **İlgili:** `architecture.md` §2, §6, §9; `annotation.md` §1, §3.1, §3.9; `openapi.yaml` `POST /memes/ai-drafts`; ADR-0009

## Bağlam

Meme'lerin hepsini dört kişinin elle etiketlemesi uzun sürüyor. Bir LLM, meme'lerin bir kısmı için `architecture.md` §3 biçiminde kartlar hazırladı. `architecture.md` §9, anlam alanlarının LLM'e ön-doldurtulmasını reddetmişti: etiketleyici taslağa kayar, çift etiketlemede uyum yapay olarak yükselir ve LLM ile insan etiketlerini karşılaştıran deney kirlenir.

## Karar

- LLM kartları doğrudan gold olmaz. Kartı olan meme tek etiketlidir; kart, atanan annotator'ın formuna taslak olarak dolu gelir. Annotator her alanı kontrol edip düzeltir ve gönderir; reviewer ikinci bakışı yapar (ADR-0009).
- Kartı olan meme çift etiketli alt kümeye ve kalibrasyon turuna alınmaz. Uyum ve kalibrasyon taslaksız etiketlemeyle ölçülür.
- Ham kart değiştirilmeden ayrıca saklanır; annotator'ın ne kadar düzelttiği ölçülebilir.
- Kartın görsel tarifi, meme'in VLM taslağı boşsa onun yerine geçer.

## Sonuçlar

- Etiketleme hızlanır; kalite gönderim doğrulaması ve reviewer'ın ikinci bakışıyla korunur.
- Annotator'ın taslağa kayma riski kalır. Arayüz formun taslakla dolu geldiğini açıkça gösterir.
- LLM–insan karşılaştırması tek etiketli meme'lerde düzeltme miktarını ölçer; bağımsız karşılaştırma taslaksız çift etiketli alt kümede yapılır.
- `architecture.md` §9'daki "Anlam alanlarını LLM'e ön-doldurtmak" maddesi tek etiketli meme'ler için geçerliliğini yitirir.
