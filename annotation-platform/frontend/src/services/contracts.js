/** Shared values and payload documentation mirrored from annotation-platform/openapi.yaml. */
export const ANNOTATION_STATUS = Object.freeze(['atandi', 'devam_ediyor', 'gonderildi', 'revizyon_gerekli', 'onaylandi', 'atlandi'])
export const SKIP_REASONS = Object.freeze(['tanimiyorum', 'tanidiklik_dusuk', 'uygun_degil', 'diger'])
export const COMMENT_TYPES = Object.freeze(['soru', 'kilavuz_onerisi', 'kopya_suphesi', 'hata'])
export const TEST_QUERY_MODES = Object.freeze(['durum', 'tarif'])
export const LABEL_FIELDS = Object.freeze(['duygu', 'niyet', 'mekanizma', 'uyari'])
export const EXPORT_FILES = Object.freeze(['gold.jsonl', 'annotations_raw.jsonl', 'test_set.jsonl'])
export const CONFIDENCE_VALUES = Object.freeze([1, 2, 3])

/** @typedef {{alan:string, kural:string, mesaj:string}} FieldError (OpenAPI FieldError) */
/** @typedef {{gecerli:boolean, hatalar:FieldError[]}} ValidationResult */
/** @typedef {{surum:number, icerik?:Object, tanidiklik?:number, alan_guveni?:Record<string, 1|2|3>, aktif_sure_artis_sn?:number}} AnnotationDraft */
/** @typedef {{gerekce:'tanimiyorum'|'tanidiklik_dusuk'|'uygun_degil'|'diger', aciklama?:string|null, tanidiklik?:number}} SkipRequest */
/** @typedef {{metin:string, mod:'durum'|'tarif', dogru_memeler:string[]}} TestQueryCreate */
/** @typedef {{icerik:Object, kaynak_annotationlar:string[], cozum_notu?:string|null}} GoldCreate */
/** @typedef {{meme_ids:string[], annotator_id:string, cift_etiket?:boolean, kalibrasyon?:boolean}} AssignmentCreate */
/** @typedef {{id:string, gorsel_url:string, kucuk_gorsel_url:string, sha256:string, etiket_durumu:string, annotatorlar:Object[], cift_etiket?:boolean, gold_var:boolean}} Meme */
/** @typedef {Meme & {annotasyonlar?:Object[]}} MemeDetail */
/** @typedef {{annotation_id:string, meme_id:string, kucuk_gorsel_url:string, durum_kodu:string, cift_etiket:boolean, kalibrasyon:boolean, revizyon_notu?:string|null}} QueueItem */
/** @typedef {{id:string, meme_id:string, durum_kodu:string, cift_etiket:boolean, kalibrasyon:boolean, icerik:Object, tanidiklik?:number|null, alan_guveni?:Record<string,1|2|3>, surum:number}} Annotation */
/** @typedef {{id:string, meme_id:string, yazan:Object, zaman:string, metin:string, tur:'soru'|'kilavuz_onerisi'|'kopya_suphesi'|'hata', cozuldu:boolean}} Comment */
/** @typedef {{meme:Object, annotasyonlar:Annotation[], karsilastirma:Object[]}} ReviewDetail */
/** @typedef {{id:string, metin:string, mod:'durum'|'tarif', dogru_memeler:string[], yazan:Object, zaman:string}} TestQuery */
/** @typedef {{alanlar:Record<string,Object>, sema_versiyonu:string}} AnnotationSchema */
/** @typedef {{versiyon:string, olusturma_zamani:string, alanlar:Record<string,Object[]>}} LabelList */

export function createEmptyAnnotationContent() {
  return {
    tur: null,
    ad: '',
    kaynak: '',
    durum: '',
    ornek_durumlar: [],
    uygun_olmayan_durumlar: [],
    kulturel_bilgi: '',
    duygu: [],
    niyet: [],
    mekanizma: [],
    uyari: null,
    notlar: '',
  }
}

/**
 * Fast client feedback based on GET /schema/annotation. The API's validate/submit
 * endpoints remain authoritative and are always called before submission.
 * @param {Object} content AnnotationContent
 * @param {Object} schema AnnotationSchema response
 * @param {Object} labels LabelList.alanlar
 * @returns {FieldError[]}
 */
export function validateAnnotationLocally(content, schema, labels = {}) {
  const errors = []
  const rules = schema?.alanlar || {}
  for (const [field, rule] of Object.entries(rules)) {
    const value = content[field]
    const missing = value === undefined || value === null || (typeof value === 'string' && !value.trim())
    const isWarningExplicitlyEmpty = field === 'uyari' && Array.isArray(value) && value.length === 0
    if (rule.zorunlu && missing) {
      errors.push({ alan: field, kural: 'zorunlu', mesaj: field === 'uyari' ? 'Bir uyarı seç veya bilinçli olarak “uyarı yok” seçimini onayla.' : 'Bu alan zorunludur.' })
      continue
    }
    if (missing || isWarningExplicitlyEmpty) continue

    if (rule.tip === 'metin' && typeof value === 'string' && rule.min_karakter && value.trim().length < rule.min_karakter) {
      errors.push({ alan: field, kural: 'min_karakter', mesaj: `En az ${rule.min_karakter} karakter olmalı.` })
    }
    if (rule.tip === 'enum' && Array.isArray(rule.degerler) && !rule.degerler.includes(value)) {
      errors.push({ alan: field, kural: 'gecersiz_etiket', mesaj: 'Geçerli seçeneklerden birini seç.' })
    }
    if (rule.tip === 'metin_listesi' || rule.tip === 'etiket_listesi') {
      if (!Array.isArray(value)) {
        errors.push({ alan: field, kural: 'zorunlu', mesaj: 'Liste biçiminde değer girilmeli.' })
        continue
      }
      if (rule.min_adet !== undefined && value.length < rule.min_adet) errors.push({ alan: field, kural: 'min_adet', mesaj: `En az ${rule.min_adet} öğe seçilmeli.` })
      if (rule.max_adet !== undefined && value.length > rule.max_adet) errors.push({ alan: field, kural: 'max_adet', mesaj: `En fazla ${rule.max_adet} öğe seçilebilir.` })
      if (rule.tekrarsiz && new Set(value.map((item) => String(item).trim().toLocaleLowerCase('tr-TR'))).size !== value.length) errors.push({ alan: field, kural: 'tekrar', mesaj: 'Liste öğeleri birbirinden farklı olmalı.' })
      if (rule.tip === 'etiket_listesi') {
        const active = new Set((labels[rule.etiket_alani || field] || []).filter((item) => item.aktif).map((item) => item.etiket))
        value.forEach((item) => { if (!active.has(item)) errors.push({ alan: field, kural: 'gecersiz_etiket', mesaj: 'Etkin etiket listesinden seçim yap.' }) })
      }
    }
  }
  return errors
}
