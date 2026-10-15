/** OpenAPI 3.0.3 client for ../openapi.yaml (base path: /api/v1). */
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '')
const TOKEN_KEY = 'memescout_access_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

export class ApiError extends Error {
  constructor(status, payload) {
    const contractError = payload?.hata
    super(contractError?.mesaj || payload?.detail || `İstek başarısız (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.code = contractError?.kod
    this.fields = contractError?.alanlar || []
    this.details = contractError?.detay || {}
    if (this.code === 'SURUM_CAKISMASI') this.message = 'Bu annotation başka bir sekmede güncellendi. Sayfayı yenileyip son taslağı yükle.'
    if (this.code === 'TANIDIKLIK_DUSUK') this.message = 'Tanıdıklık 1 veya 2 olduğu için bu annotation gönderilemez; atlanıp yeniden atanmalı.'
    if (this.code === 'REVIEWER_ANNOTATOR_OLAMAZ') this.message = 'Memi etiketleyen kişi bu meme için reviewer olamaz.'
    if (this.code === 'KOPYA') this.message = `Aynı görsel daha önce yüklenmiş${this.details.mevcut_meme_id ? ` (${this.details.mevcut_meme_id})` : ''}.`
    if (this.code === 'SIZINTI') {
      const memes = this.details.ihlal_eden_memeler || []
      this.message = memes.length
        ? `Sızıntı kuralı: katkı verdiğin şu meme(ler) doğru cevap olamaz: ${memes.join(', ')}.`
        : 'Bu test sorgusu sızıntı kuralını ihlal ediyor. Doğru meme seçimini değiştir.'
    }
  }
}

const idPath = (id) => encodeURIComponent(id)
const queryString = (params = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    query.set(key, typeof value === 'boolean' ? String(value) : String(value))
  })
  const result = query.toString()
  return result ? `?${result}` : ''
}

async function request(path, { body, token = getToken(), headers = {}, ...options } = {}) {
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body === undefined ? undefined : (isForm ? body : JSON.stringify(body)),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new ApiError(response.status, payload)
  }
  if (response.status === 204) return null
  const type = response.headers.get('content-type') || ''
  return type.includes('application/json') ? response.json() : response.blob()
}

const json = (method, body) => ({ method, body })

/**
 * Request helpers mirror every path and HTTP method in the OpenAPI contract.
 * The backend remains authoritative for role, state, reviewer and leakage rules.
 */
export const api = {
  // Auth & users
  login: (kullanici_adi, sifre) => request('/auth/login', { ...json('POST', { kullanici_adi, sifre }), token: null }),
  register: (kullanici_adi, sifre) => request('/auth/register', { ...json('POST', { kullanici_adi, sifre }), token: null }),
  me: () => request('/auth/me'),
  users: () => request('/users'),
  createUser: (user) => request('/users', json('POST', user)),

  // Schema & versioned label lists
  schema: () => request('/schema/annotation'),
  labels: (versiyon) => request(`/label-lists${queryString({ versiyon })}`),
  labelVersions: () => request('/label-lists/versions'),
  createLabel: (label) => request('/label-lists/labels', json('POST', label)),
  updateLabel: (alan, etiket, changes) => request(`/label-lists/labels/${idPath(alan)}/${idPath(etiket)}`, json('PATCH', changes)),

  // Meme inventory, protected images and gold records
  memes: (filters = {}) => request(`/memes${queryString({ etiket_durumu: filters.etiket_durumu, annotator_id: filters.annotator_id, cift_etiket: filters.cift_etiket, q: filters.q, sayfa: filters.sayfa, boyut: filters.boyut })}`),
  meme: (memeId) => request(`/memes/${idPath(memeId)}`),
  image: (memeId, boyut = 'orijinal') => request(`/memes/${idPath(memeId)}/image${queryString({ boyut })}`),
  gold: (memeId) => request(`/memes/${idPath(memeId)}/gold`),
  uploadMeme: (file) => { const form = new FormData(); form.append('dosya', file); return request('/memes', { method: 'POST', body: form }) },
  uploadMemes: (files) => { const form = new FormData(); [...files].forEach((file) => form.append('dosyalar', file)); return request('/memes/bulk', { method: 'POST', body: form }) },

  // Comments: GET response is already filtered by the server's blind-annotation rule.
  memeComments: (memeId) => request(`/memes/${idPath(memeId)}/comments`),
  addMemeComment: (memeId, comment) => request(`/memes/${idPath(memeId)}/comments`, json('POST', comment)),
  comments: (filters = {}) => request(`/comments${queryString({ cozuldu: filters.cozuldu, tur: filters.tur, sayfa: filters.sayfa, boyut: filters.boyut })}`),
  updateComment: (commentId, cozuldu) => request(`/comments/${idPath(commentId)}`, json('PATCH', { cozuldu })),

  // Assignments (admin)
  createAssignment: (assignment) => request('/assignments', json('POST', assignment)),
  autoAssign: (plan) => request('/assignments/auto', json('POST', plan)),
  reassign: (annotationId, yeni_annotator_id) => request(`/annotations/${idPath(annotationId)}/reassign`, json('POST', { yeni_annotator_id })),

  // Annotation lifecycle
  queue: (durum_kodu) => request(`/me/queue${queryString({ durum_kodu: Array.isArray(durum_kodu) ? durum_kodu.join(',') : durum_kodu })}`),
  annotation: (annotationId) => request(`/annotations/${idPath(annotationId)}`),
  start: (annotationId) => request(`/annotations/${idPath(annotationId)}/start`, { method: 'POST' }),
  saveDraft: (annotationId, draft, keepalive = false) => request(`/annotations/${idPath(annotationId)}/draft`, { ...json('PATCH', draft), keepalive }),
  validate: (annotationId) => request(`/annotations/${idPath(annotationId)}/validate`, { method: 'POST' }),
  submit: (annotationId, surum) => request(`/annotations/${idPath(annotationId)}/submit`, json('POST', { surum })),
  skip: (annotationId, skip) => request(`/annotations/${idPath(annotationId)}/skip`, json('POST', skip)),
  annotationVersions: (annotationId) => request(`/annotations/${idPath(annotationId)}/versions`),
  requestRevision: (annotationId, not) => request(`/annotations/${idPath(annotationId)}/request-revision`, json('POST', { not })),

  // Reviewer queue and gold approval. The API rejects a reviewer who annotated that meme.
  reviews: () => request('/reviews'),
  review: (memeId) => request(`/reviews/${idPath(memeId)}`),
  approveGold: (memeId, gold) => request(`/reviews/${idPath(memeId)}/gold`, json('POST', gold)),

  // Test queries. createTestQuery performs a client-side leakage preflight and still relies on server validation.
  testQueries: (filters = {}) => request(`/test-queries${queryString({ yazan_id: filters.yazan_id, mod: filters.mod })}`),
  createTestQuery: (query) => request('/test-queries', json('POST', query)),
  updateTestQuery: (queryId, changes) => request(`/test-queries/${idPath(queryId)}`, json('PATCH', changes)),
  deleteTestQuery: (queryId) => request(`/test-queries/${idPath(queryId)}`, { method: 'DELETE' }),

  // Statistics & admin tools
  progressStats: () => request('/stats/progress'),
  agreementStats: () => request('/stats/agreement'),
  recheck: () => request('/recheck'),
  audit: (filters = {}) => request(`/audit${queryString({ kayit_tipi: filters.kayit_tipi, kayit_id: filters.kayit_id, kullanici_id: filters.kullanici_id, sayfa: filters.sayfa, boyut: filters.boyut })}`),
  exportFile: (filename) => {
    if (!['gold.jsonl', 'annotations_raw.jsonl', 'test_set.jsonl'].includes(filename)) throw new TypeError('Desteklenmeyen dışa aktarım dosyası.')
    return request(`/export/${encodeURIComponent(filename)}`)
  },
}

/**
 * Client-side defense for test-query answer leakage. It inspects only the current user's
 * own annotation summaries and the gold reviewer. It never requests another annotator's
 * private annotation content. Any unverifiable candidate is rejected closed; the server
 * still performs the complete source-annotation/reviewer check on POST /test-queries.
 */
export async function checkTestQueryLeakage(authorId, memeIds) {
  const violations = []
  const checks = await Promise.all(memeIds.map(async (memeId) => {
    let meme
    let gold
    try { [meme, gold] = await Promise.all([api.meme(memeId), api.gold(memeId)]) }
    catch (cause) {
      if (cause.status === 403) throw new Error(`${memeId}: katkı bilgisi kör etiketleme nedeniyle doğrulanamadı. Bu memi sorguya ekleme.`)
      if (cause.status === 404) throw new Error(`${memeId}: gold kaydı bulunamadı. Yalnızca doğrulanmış gold memeleri seç.`)
      throw cause
    }
    const ownAnnotation = (meme.annotasyonlar || []).some((item) => item.annotator?.id === authorId)
    const ownAsReviewer = gold.reviewer?.id === authorId
    return { memeId, violation: ownAnnotation || ownAsReviewer }
  }))
  checks.forEach(({ memeId, violation }) => { if (violation) violations.push(memeId) })
  if (violations.length) {
    const error = new ApiError(422, { hata: { kod: 'SIZINTI', mesaj: 'Sızıntı kuralı ihlali.', detay: { ihlal_eden_memeler: violations } } })
    throw error
  }
  return true
}

export function imageUrl(id) {
  return `${API_BASE}/memes/${idPath(id)}/image?boyut=orijinal`
}
