\================================================================================  
MEMESCOUT — ANNOTATION PLATFORMU VE VERİ ŞEMASI TASARIMI  
\================================================================================  
Doküman Sürümü : v2.0.0  
Hedef          : Data Engineering & Annotation Platform Spec  
Model Kapsamı  : Multi-Vector Dense Semantic Space (BAAI/bge-m3, ytu-ce-cosmos)  
İşleyiş Mantığı: Zero-LLM Inference, Single-Annotator Architecture, Multi-Vector  
\================================================================================

1\. AMAÇ VE KAPSAM  
\--------------------------------------------------------------------------------  
\- Veri Hacmi: \~300–500 meme görseli ve GIF şablonu.  
\- Etiketleme Modeli (Tekil Sorumluluk):  
  4 kişinin aynı anda veri girerken yaratacağı stil kargaşasını ve çakışmaları  
  önlemek için tüm veri kümesi tek bir birincil annotator tarafından tutarlı bir  
  dil ve derinlikle etiketlenir. Ekibin diğer üyeleri sistemde izleyici (viewer)  
  veya değerlendirici (evaluator) olarak yer alır; veri üzerinde yetki karmaşası  
  yaşanmaz.  
\- Sıfır LLM Runtime İllüzyonu:  
  Arama anında arkada devasa LLM'ler her sorguda çalıştırılmaz. Anlamsal kavrayış  
  ve mizah sezgisi, veriye önceden enjekte edilen akıllı etiketler, pozitif/negatif  
  örnek durumlar ve Türkçe dense embedding modellerinin (bge-m3, ytu-cosmos)  
  latent uzay yakınsamasıyla sağlanır. LLM yalnızca opsiyonel/kritik karar  
  aşamalarında (sorgu niyetini ayrıştırma veya son Top-5 adayı mizahi açıdan  
  gerekçelendirme) devreye girer.  
\- Çıktı: Doğrudan çoklu vektör arama motorunun besleneceği kesinleşmiş altın veri  
  (gold.jsonl) ve sızıntı korumalı test seti (test\_set.jsonl).

2\. ROLLER VE YETKİLER  
\--------------------------------------------------------------------------------  
\- Annotator (Tekil Etiketleyici):  
  Tek kişidir. Tüm meme'leri hem görsel (V\_visual) hem bağlamsal (V\_context)  
  boyutlarıyla tek elden etiketler, taslak kaydeder ve teslim eder.  
\- Reviewer / Viewer (İzleyici & Denetçi):  
  Ekibin diğer 3 üyesidir. Etiketleri inceler, yorum bırakabilir, ancak veri  
  çakışmasını önlemek için doğrudan alanları ezemez. Gerekirse revizyon notu düşer.  
\- Admin:  
  Görsel/GIF yükler, etiket listelerini yönetir, gold.jsonl dışa aktarımı alır.

3\. VERİ MODELİ VE DOĞRULAMA ŞEMASI  
\--------------------------------------------------------------------------------  
Meme (Görsel / Dosya)  
 │  
 ├── Annotation (Tekil Annotator — İçerik ve Vektör Alanları)  
 ├── Yorum / İşaret (Ekip İçi Geri Bildirim)  
 └── TestSorgusu (Sızıntı Korumalı Doğrulama Seti)

3.1 Meme (Görsel Bilgisi)  
Yükleme anında sistem tarafından otomatik oluşturulur:  
\- id: Tekil kimlik (dosya\_adi veya slug)  
\- gorsel\_yolu: Dosyanın depolandığı yer (memes/aglayan\_canta.png)  
\- medya\_tipi: enum (image veya gif)  
\- sha256: Dosyadan hesaplanan hash; mükerrer yüklemeleri engeller  
\- yuklenme\_zamani: Yükleme anı (UTC)

3.2 Annotation (İçerik Şeması — Çoklu Vektör ve Alan Ağırlıklandırma)  
Arama motorunda kullanıcı iki farklı niyetle gelebilir:  
1\. Görsel/Nesne Araması: "Sırtında okul çantası olan ağlayan köpek" \-\> V\_visual baskın çalışır.  
2\. Durum/Reaksiyon Araması: "Finallerden kaldım, hayatım karardı" \-\> V\_context baskın çalışır.

Embedding seyreltmesini (dilution) önlemek adına alanlar fiziksel ve bağlamsal  
olarak ayrılmıştır:

\- tur: enum, Zorunlu ('template' veya 'hazir\_meme')  
\- ad: string, Zorunlu (Min 3, Max 60 karakter) \- Meme'in popüler adı.  
\- kaynak: string, Opsiyonel (Max 100 karakter) \- Eser, film, sahne veya köken.  
\- gorsel\_tanim: metin, Zorunlu (Min 20, Max 120 karakter)  
  \[V\_visual Vektör Kaynağı\]: Sadece kameranın gördüğü somut varlıklar (renk,  
  nesne, kişi, hayvan). Duygu veya soyut yorum YAZILMAZ.  
\- durum: metin, Zorunlu (Min 30, Max 150 karakter)  
  \[V\_context Pozitif Çekirdeği\]: Olayın soyut iskeleti (Örn: "Ağır sorumluluklar  
  karşısında çaresiz bıkkınlık").  
\- ornek\_durumlar: liste, Zorunlu (3–5 adet)  
  \[Pozitif Vektör Güçlendiricisi\]: Bu meme'in nokta atışı oturacağı somut senaryolar  
  (Örn: "Pazar gecesi bitmeyen ödevlerle yüzleşmek").  
\- uygun\_olmayan\_durumlar: liste, Zorunlu (1–2 adet)  
  \[Negatif Vektör / Ceza Puanı\]: Modelin yanlış eşleşmesini önleyecek durumlar.  
  Sorgu buraya yakınsa benzerlik skoru kırılır (Örn: "Gerçek bir vefat veya kaza haberi").  
\- es\_anlam\_ve\_slang: liste, Zorunlu (3–8 anahtar kelime)  
  \[Akıllı Manipülasyon\]: Kullanıcının yazabileceği günlük konuşma dili, argo ve  
  deyimler (Örn: \["bıkmak", "daralmak", "patlamak", "vizeler", "okul zulmü"\]).  
\- kulturel\_bilgi: metin, Zorunlu (Min 30, Max 250 karakter)  
  Neden komik olduğu ve Türk kültüründeki karşılığı.  
\- duygu: liste, Zorunlu (1–3 etiket) \- Sabit listeden (ADR-0008 snake\_case).  
\- niyet: liste, Zorunlu (1–3 etiket) \- Sabit listeden.  
\- mekanizma: liste, Zorunlu (1–3 etiket) \- Sabit listeden.  
\- uyari: liste, Zorunlu (ADR-0004 standardı: null: cevaplanmadı, \[\]: uyarı yok,  
  \["politik", "kaba\_argo", "hassas"\]).  
\- notlar: metin, Opsiyonel (Max 300 karakter).

4\. ARAMA MOTORU İÇİN VEKTÖR DERLEME VE PUANLAMA  
\--------------------------------------------------------------------------------  
4.1 Vektör Girdileri  
\- TEXT\_FOR\_V\_VISUAL:  
  "{gorsel\_tanim}"

\- TEXT\_FOR\_V\_CONTEXT:  
  "{durum}. Örnekler: {'. '.join(ornek\_durumlar)}. Kavramlar: {', '.join(es\_anlam\_ve\_slang)}. Ton: {duygu, niyet}"

\- TEXT\_FOR\_V\_NEGATIVE:  
  "{'. '.join(uygun\_olmayan\_durumlar)}"

4.2 Puanlama Formülü (Pozitif Eşleşme ve Ceza Puanı)  
Kullanıcı sorgusu q geldiğinde:  
  S\_visual   \= CosineSim(E\_q, V\_visual)  
  S\_context  \= CosineSim(E\_q, V\_context)  
  P\_negative \= CosineSim(E\_q, V\_negative)

  Final\_Score \= (W\_visual \* S\_visual) \+ (W\_context \* S\_context) \- (lambda \* P\_negative)

(Burada lambda ≈ 0.25 ceza katsayısıdır. Kullanıcı nesne/tarif arıyorsa W\_visual=0.7,  
his/durum arıyorsa W\_context=0.8 seçilir).

5\. TEST SORGUSU VE SIZINTI KORUMASI (ADR-0002)  
\--------------------------------------------------------------------------------  
\- Değerlendirme seti (\~100 sorgu) platform üzerinden girilir.  
\- Sızıntı Kuralı: Veri tek bir annotator tarafından girildiği için, test sorgularını  
  annotator dışındaki diğer 3 ekip üyesi yazmak zorundadır.  
\- Bir sorgu doğru cevap olarak bir meme'i gösterdiğinde, sorguyu yazan kişi o  
  meme'in etiketleyicisi olamaz. Platform bunu denetler ve ihlalde 422 SIZINTI döner.

6\. ETİKETLEME İŞ AKIŞI  
\--------------------------------------------------------------------------------  
1\. Ön Hazırlık: Etiket listeleri (ADR-0008 snake\_case) sisteme yüklenir.  
2\. Tek Elden Etiketleme:  
   \- Birincil annotator tüm görselleri sırayla açar.  
   \- Solda görseli görür, sağda formu doldurur.  
   \- Her meme için fiziksel tanımı (gorsel\_tanim) ve kullanım bağlamını (durum, es\_anlam\_ve\_slang) doldurur.  
   \- Negatif senaryoyu (uygun\_olmayan\_durumlar) belirterek ceza vektörünü kurar.  
3\. Ekip Denetimi (Review & Discussion):  
   \- Diğer 3 üye sisteme girerek etiketleri inceler.  
   \- Kültürel bir hata veya eksik slang varsa yorum (/comments) bırakır.  
4\. Test Seti Oluşturma: Diğer 3 üye, sızıntı kuralına uygun olarak gerçekçi kullanıcı  
   sorgularını sisteme ekler.  
5\. Dışa Aktarım (gold.jsonl): Onaylanan kayıtlar arama motoruna aktarılır.

7\. PLATFORM ÖZELLİKLERİ (UI / UX)  
\--------------------------------------------------------------------------------  
\- Fiziksel vs Bağlam Ayrımı: Form ekranında 'Görsel Tarif' alanı ile 'Kullanım Durumu & Slang'  
  alanları farklı renk bloklarıyla ayrılır; annotator'ın kavramları karıştırması önlenir.  
\- Canlı Karakter Sayacı: min ve max karakter sınırları canlı gösterilir, sınır dışına  
  çıkıldığında kaydetme uyarısı verir.  
\- Uyarı Kutusu (ADR-0004): 'Uyarı Yok' ayrı bir checkbox olarak işaretlenmeden form  
  onaylanamaz (uyari: null engeli).  
\- Otomatik Taslak Kaydı: Her 5 saniyede bir PATCH /annotations/{id}/draft ile kaydedilir  
  (sürüm çakışması korumalı).  
\- Mükerrer Kontrolü: Yüklenen görsellerde SHA256 kontrolü ile kopya meme engellenir.  
\================================================================================  
