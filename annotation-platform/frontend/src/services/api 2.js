const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')
const TOKEN_KEY = 'memescout_access_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

export class ApiError extends Error {
  constructor(status, payload) {
    super(payload?.hata?.mesaj || payload?.detail || `İstek başarısız (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.code = payload?.hata?.kod
    this.fields = payload?.hata?.alanlar || []
    this.details = payload?.hata?.detay
  }
}

async function request(path, { body, token = getToken(), headers = {}, ...options } = {}) {
  const isForm = body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(body && !isForm ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new ApiError(response.status, payload)
  }
  if (response.status === 204) return null
  const type = response.headers.get('content-type') || ''
  return type.includes('application/json') ? response.json() : response.blob()
}

const idPath = (id) => encodeURIComponent(id)

export const api = {
  login: (kullanici_adi, sifre) => request('/auth/login', { method: 'POST', token: null, body: { kullanici_adi, sifre } }),
  me: () => request('/auth/me'),
  schema: () => request('/schema/annotation'),
  labels: () => request('/label-lists'),
  queue: () => request('/me/queue', { method: 'GET' }),
  annotation: (id) => request(`/annotations/${idPath(id)}`),
  image: (id, size = 'orijinal') => request(`/memes/${idPath(id)}/image?boyut=${size}`),
  start: (id) => request(`/annotations/${idPath(id)}/start`, { method: 'POST' }),
  saveDraft: (id, draft, keepalive = false) => request(`/annotations/${idPath(id)}/draft`, { method: 'PATCH', body: draft, keepalive }),
  validate: (id) => request(`/annotations/${idPath(id)}/validate`, { method: 'POST' }),
  submit: (id, surum) => request(`/annotations/${idPath(id)}/submit`, { method: 'POST', body: { surum } }),
  skip: (id, body) => request(`/annotations/${idPath(id)}/skip`, { method: 'POST', body }),
}

export function imageUrl(id) {
  return `${API_BASE}/memes/${idPath(id)}/image?boyut=orijinal`
}
