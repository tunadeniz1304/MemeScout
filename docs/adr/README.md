# Mimari Karar Kayıtları (ADR)

Bu klasör, MemeScout'ta alınan önemli teknik kararları ve gerekçelerini tutar.
Her karar ayrı bir dosyadadır: `NNNN-kisa-ad.md`. Numaralar artarak gider, eski numaralar yeniden kullanılmaz.

Bir karar değişirse eski kaydı silmeyin; durumunu "Yerini aldı: ADR-NNNN" yapıp yeni bir kayıt açın.

**Durumlar:** Önerildi · Kabul edildi · Reddedildi · Yerini aldı

| No | Karar | Durum |
|---|---|---|
| [0001](0001-api-contract-tek-kaynak.md) | API contract tek doğru kaynak | Kabul edildi |
| [0002](0002-sizinti-kurali-reviewer-dahil.md) | Sızıntı kuralı gold kayda katkı veren herkesi kapsar | Kabul edildi |
| [0003](0003-kor-etiketlemede-yorumlar-gizli.md) | Kör etiketleme yorumları da kapsar | Kabul edildi |
| [0004](0004-uyari-null-ve-bos-liste.md) | `uyari` alanında `null` ve `[]` ayrımı | Kabul edildi |
| [0005](0005-annotation-ek-alanlari.md) | Annotation'a `kalibrasyon`, `surum`, `revizyon_notu` alanları | Kabul edildi |
| [0006](0006-gold-annotator-liste.md) | `gold.jsonl`'de `annotator` alanı liste | Kabul edildi |
| [0007](0007-ek-api-islemleri.md) | Dokümanda olmayan ek API işlemleri | Kabul edildi |
| [0008](0008-etiket-sistem-adlari.md) | Etiketlerin sistem adları | Kabul edildi |
| [0009](0009-tek-etiketli-memelerde-ikinci-bakis.md) | Tek etiketli meme'lerde hafif ikinci bakış | Kabul edildi |
| [0010](0010-tek-etiketli-memelerde-llm-taslagi.md) | Tek etiketli meme'lerde LLM taslağı | Kabul edildi |
| [0011](0011-kullanilmasin-oyu-ve-havuz.md) | Kullanılmayacak meme'ler için oy ve havuz | Kabul edildi |

## Şablon

```markdown
# ADR-NNNN: Başlık

- **Durum:** Önerildi
- **Tarih:** YYYY-AA-GG
- **İlgili:** dosya, bölüm veya issue

## Bağlam
Neden bir karar gerekti? Sorun ne?

## Karar
Ne yapmaya karar verdik?

## Sonuçlar
Bu kararın getirdiği kazançlar, maliyetler ve yapılması gereken işler.
```
