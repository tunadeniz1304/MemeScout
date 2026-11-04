import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, clearToken, getToken, setToken } from './services/api'
import { EXCLUSION_NOTE_MAX, EXCLUSION_REASONS, MEME_STATUS_NAMES, createEmptyAnnotationContent, exclusionReasonName, validateAnnotationLocally } from './services/contracts'

const blankContent = createEmptyAnnotationContent
const fieldNames = { tur: 'Meme türü', ad: 'Meme adı', kaynak: 'Kaynak', vlm_aciklama: 'Görsel tarif', durum: 'Genel durum', ornek_durumlar: 'Örnek durumlar', uygun_olmayan_durumlar: 'Uygun olmayan durumlar', kulturel_bilgi: 'Kültürel bilgi', anahtar_kelimeler: 'Anahtar kelimeler', duygu: 'Duygu', niyet: 'Niyet', mekanizma: 'Mizah mekanizması', uyari: 'Uyarılar', notlar: 'Notlar' }
const characterHint = (rule) => rule.tip === 'metin_listesi' ? (rule.max_karakter ? `Her biri en fazla ${rule.max_karakter} karakter` : '') : rule.min_karakter && rule.max_karakter ? `${rule.min_karakter}–${rule.max_karakter} karakter` : rule.min_karakter ? `En az ${rule.min_karakter} karakter` : rule.max_karakter ? `En fazla ${rule.max_karakter} karakter` : ''
const registrationOpen = import.meta.env.VITE_REGISTRATION_OPEN === '1'

function Brand() {
  return <div className="brand"><span className="brand-mark">m</span><span>MemeScout</span></div>
}

function Login({ onLogin, onRegister, error, busy }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState('login')
  const registering = mode === 'register'
  return <main className="login-shell"><section className="login-card"><Brand /><p className="eyebrow">ETİKETLEME PLATFORMU</p><h1>{registering ? 'Hesap oluştur.' : 'Tekrar hoş geldin.'}</h1><p className="muted">{registering ? 'Kullanıcı adın ve şifrenle MemeScout’a katıl.' : 'Etiketleme kuyruğuna erişmek için giriş yap.'}</p><form onSubmit={(event) => { event.preventDefault(); (registering ? onRegister : onLogin)(username, password) }} className="login-form"><label>Kullanıcı adı<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} minLength={registering ? 3 : undefined} maxLength={registering ? 64 : undefined} pattern={registering ? '[A-Za-z0-9_.-]+' : undefined} required /></label><label>Şifre<input type="password" autoComplete={registering ? 'new-password' : 'current-password'} value={password} onChange={(event) => setPassword(event.target.value)} minLength={registering ? 8 : undefined} maxLength={registering ? 128 : undefined} required /></label>{registering && <p className="field-hint">Kullanıcı adı en az 3 karakter; şifre en az 8 karakter olmalı.</p>}{error && <p className="error-banner">{error}</p>}<button className="button primary full" disabled={busy}>{busy ? (registering ? 'Hesap oluşturuluyor…' : 'Giriş yapılıyor…') : (registering ? 'Üye ol' : 'Giriş yap')} <span>→</span></button></form>{registrationOpen && <button type="button" className="auth-toggle" onClick={() => setMode(registering ? 'login' : 'register')}>{registering ? 'Zaten hesabın var mı? Giriş yap' : 'Hesabın yok mu? Üye ol'}</button>}<p className="login-foot">MemeScout · SENG 429</p></section></main>
}

function MultiText({ value = [], onChange, placeholder }) {
  const [draft, setDraft] = useState('')
  const add = () => { const text = draft.trim(); if (text && !value.includes(text)) onChange([...value, text]); setDraft('') }
  return <div className="multi-text">{value.map((item, index) => <div className="list-entry" key={`${item}-${index}`}><span>{item}</span><button type="button" aria-label="Satırı sil" onClick={() => onChange(value.filter((_, i) => i !== index))}>×</button></div>)}<div className="inline-input"><input value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); add() } }} placeholder={placeholder || 'Bir madde yaz…'} /><button type="button" className="button secondary small" onClick={add}>Ekle</button></div></div>
}

function LabelPicker({ field, labels = [], value = [], onChange }) {
  const choices = labels.filter((label) => label.aktif !== false)
  const stale = value.filter((tag) => !choices.some((label) => label.etiket === tag))
  const toggle = (tag) => onChange(value.includes(tag) ? value.filter((item) => item !== tag) : [...value, tag])
  return <div className="label-picker">{choices.map((label) => <button type="button" key={label.etiket} className={`tag-option ${value.includes(label.etiket) ? 'selected' : ''}`} title={label.tanim} onClick={() => toggle(label.etiket)}><span>{value.includes(label.etiket) ? '✓' : '+'}</span>{label.gorunen_ad}</button>)}{stale.map((tag) => <button type="button" key={tag} className="tag-option selected stale" title="Bu etiket artık listede etkin değil; kaldırmak için tıkla." onClick={() => toggle(tag)}><span>×</span>{labels.find((label) => label.etiket === tag)?.gorunen_ad || tag} (pasif)</button>)}{choices.length === 0 && <p className="muted tiny">Etiket listesi yüklenemedi.</p>}</div>
}

function Field({ name, rule = {}, content, update, labels, errors = [], confidence, updateConfidence }) {
  const title = fieldNames[name] || name.replaceAll('_', ' ')
  const required = rule.zorunlu
  const error = errors.find((item) => item.alan === name || item.alan?.startsWith(`${name}[`))
  const label = <div className="field-heading"><label htmlFor={name}>{title}{required && <span className="required"> *</span>}</label>{characterHint(rule) && <span className="field-hint">{characterHint(rule)}</span>}{rule.max_adet && <span className="field-hint">En fazla {rule.max_adet} seçim</span>}</div>
  let control
  if (name === 'uyari') {
    const noWarning = Array.isArray(content.uyari) && content.uyari.length === 0
    control = <><label className={`no-warning ${noWarning ? 'checked' : ''}`}><input type="checkbox" checked={noWarning} onChange={(event) => update('uyari', event.target.checked ? [] : null)} /><span className="checkmark">{noWarning ? '✓' : ''}</span><span><strong>Bilinçli uyarı yok</strong><small>Bu meme için uyarı gerekmediğini onaylıyorum.</small></span></label>{!noWarning && <LabelPicker field={name} labels={labels.uyari || []} value={content.uyari || []} onChange={(value) => update('uyari', value)} />}{content.uyari === null && <p className="field-hint warning-hint">Bir uyarı seç veya “Bilinçli uyarı yok” kutusunu işaretle.</p>}</>
  } else if (rule.tip === 'etiket_listesi' || ['duygu', 'niyet', 'mekanizma'].includes(name)) {
    control = <LabelPicker field={name} labels={labels[rule.etiket_alani || name] || []} value={content[name] || []} onChange={(value) => update(name, value)} />
  } else if (rule.tip === 'metin_listesi' || Array.isArray(content[name])) {
    control = <MultiText value={content[name] || []} onChange={(value) => update(name, value)} />
  } else if (rule.tip === 'enum' || name === 'tur') {
    const options = rule.degerler || ['template', 'hazir_meme']
    control = <div className="radio-row">{options.map((option) => <label className={`radio-card ${content[name] === option ? 'active' : ''}`} key={option}><input type="radio" name={name} checked={content[name] === option} onChange={() => update(name, option)} /><span className="radio-dot" /><span>{option === 'template' ? 'Şablon' : option === 'hazir_meme' ? 'Hazır meme' : option}</span></label>)}</div>
  } else {
    control = <textarea id={name} rows={name === 'durum' || name === 'kulturel_bilgi' || name === 'notlar' ? 4 : 2} value={content[name] ?? ''} onChange={(event) => update(name, event.target.value)} placeholder={name === 'durum' ? 'Meme’in hangi durumda kullanıldığını anlat…' : 'Buraya yaz…'} />
  }
  return <div className={`field ${error ? 'has-error' : ''}`}>{label}{rule.aciklama && <p className="field-description">{rule.aciklama}</p>}{control}<div className="confidence-row"><label htmlFor={`confidence-${name}`}>Bu alandaki güvenin</label><select id={`confidence-${name}`} value={confidence[name] ?? ''} onChange={(event) => updateConfidence(name, event.target.value ? Number(event.target.value) : null)}><option value="">Belirtme</option><option value="1">1 · Emin değilim</option><option value="2">2 · Kısmen eminim</option><option value="3">3 · Eminim</option></select></div>{error && <p className="field-error">{error.mesaj}</p>}</div>
}

/** Test seti (ADR-0012): herkes aynı fotoğrafları görür ve her birine, aratınca o meme'in çıkması gereken cümleleri yazar. */
function TestQueries({ user }) {
  const [items, setItems] = useState([])
  const [memes, setMemes] = useState([])
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)

  const userId = user?.id
  const refresh = useCallback(async () => {
    if (!userId) return
    try {
      const queries = await api.testQueries({ yazan_id: userId })
      const first = await api.memes({ test_seti: true, sayfa: 1, boyut: 200 })
      const pages = Math.ceil((first.toplam || first.ogeler?.length || 0) / 200)
      const rest = await Promise.all(Array.from({ length: Math.max(0, pages - 1) }, (_, index) => api.memes({ test_seti: true, sayfa: index + 2, boyut: 200 })))
      setItems(queries); setMemes([...(first.ogeler || []), ...rest.flatMap((page) => page.ogeler || [])]); setLoaded(true)
    } catch (cause) { setError(cause.message || 'Test sorguları yüklenemedi.') }
  }, [userId])

  useEffect(() => { refresh() }, [refresh])

  if (!userId) return <div className="empty-state"><p>Oturum bilgisi yükleniyor…</p></div>

  const testIds = new Set(memes.map((meme) => meme.id))
  const isFor = (item, memeId) => item.dogru_memeler.length === 1 && item.dogru_memeler[0] === memeId
  const others = items.filter((item) => !(item.dogru_memeler.length === 1 && testIds.has(item.dogru_memeler[0])))
  const written = memes.filter((meme) => items.some((item) => isFor(item, meme.id))).length
  const remove = async (id) => {
    setError('')
    try { await api.deleteTestQuery(id); await refresh() }
    catch (cause) { setError(cause.message || 'Sorgu silinemedi.') }
  }

  return <div className="queries-page"><div className="page-heading"><div><div className="breadcrumbs">Çalışma alanı <span>›</span> Test sorguları</div><h1>Test sorguları</h1><p>Test setindeki her fotoğraf için, aratınca o meme'in çıkması gereken cümleleri yaz. Her satır ayrı bir cümle olur; yalnızca kendi yazdıkların görünür.</p></div></div>{error && <div className="toast error-banner">{error}<button onClick={() => setError('')}>×</button></div>}{!loaded && !error ? <p className="muted tiny">Test seti yükleniyor…</p> : memes.length === 0 ? <div className="empty-state"><p>Test setinde henüz fotoğraf yok. Admin test setini belirleyince burada görünür.</p></div> : <><p className="muted tiny test-progress">{memes.length} fotoğraftan {written} tanesine cümle yazdın · toplam {items.length - others.length} cümle</p><div className="test-grid">{memes.map((meme) => <TestMemeCard key={meme.id} meme={meme} queries={items.filter((item) => isFor(item, meme.id))} onSaved={refresh} onRemove={remove} onError={setError} />)}</div></>}{others.length > 0 && <section className="form-card query-list-card test-others"><div className="form-top"><div><span className="eyebrow">KAYITLARIN</span><h2>Diğer sorguların</h2></div></div><div className="query-list">{others.map((item) => <article className="query-entry" key={item.id}><span className="badge private">{item.mod === 'durum' ? 'Durum' : 'Tarif'}</span><p>{item.metin}</p><small>Doğru cevaplar: {item.dogru_memeler.join(', ')}</small><button className="text-button danger-link" onClick={() => remove(item.id)}>Sil</button></article>)}</div></section>}</div>
}

function TestMemeCard({ meme, queries, onSaved, onRemove, onError }) {
  const [text, setText] = useState('')
  const [mode, setMode] = useState('durum')
  const [busy, setBusy] = useState(false)

  const add = async (event) => {
    event.preventDefault()
    const lines = text.split('\n').map((line) => line.trim()).filter(Boolean)
    const short = lines.find((line) => line.length < 5)
    if (short) { onError(`Her cümle en az 5 karakter olmalı: "${short}"`); return }
    setBusy(true); onError('')
    try {
      // Her satır ayrı bir test sorgusu olur; doğru cevabı bu fotoğraftır.
      for (const metin of lines) await api.createTestQuery({ metin, mod: mode, dogru_memeler: [meme.id] })
      setText('')
    } catch (cause) { onError(cause.message || 'Cümle eklenemedi.') }
    finally { setBusy(false); await onSaved() }
  }

  return <article className="form-card test-card"><PoolThumb memeId={meme.id} className="test-thumb" /><div><div className="test-card-head"><strong>{meme.id}</strong><span>{queries.length} cümle</span></div>{queries.length > 0 && <ul className="test-sentences">{queries.map((item) => <li key={item.id}><span className="badge private">{item.mod === 'durum' ? 'Durum' : 'Tarif'}</span><p>{item.metin}</p><button className="text-button danger-link" disabled={busy} onClick={() => onRemove(item.id)}>Sil</button></li>)}</ul>}<form onSubmit={add}><textarea rows="3" value={text} onChange={(event) => setText(event.target.value)} placeholder="Aratınca bu meme'in çıkması gereken cümle; birden fazlaysa her satıra bir tane" /><div className="test-card-actions"><select value={mode} onChange={(event) => setMode(event.target.value)}><option value="durum">Durum</option><option value="tarif">Tarif</option></select><button className="button primary" disabled={busy || !text.trim()}>{busy ? 'Ekleniyor…' : 'Ekle'}</button></div></form></div></article>
}

function ExclusionVote({ memeId }) {
  const [vote, setVote] = useState(null)
  const [loaded, setLoaded] = useState(false)
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let active = true
    api.exclusionVote(memeId)
      .then((result) => { if (active) setVote(result) })
      .catch((cause) => { if (active && cause.status !== 404) setError(cause.message || 'Oyun yüklenemedi.') })
      .finally(() => { if (active) setLoaded(true) })
    return () => { active = false }
  }, [memeId])

  const openForm = () => { setReason(vote?.sebep || ''); setNote(vote?.not || ''); setError(''); setOpen(true) }
  const saveVote = async (event) => {
    event.preventDefault()
    if (!reason) { setError('Bir sebep seç.'); return }
    setBusy(true); setError('')
    try { setVote(await api.putExclusionVote(memeId, { sebep: reason, not: note.trim() || null })); setSaved(true); setOpen(false) }
    catch (cause) { setError(cause.message || 'Oyun kaydedilemedi.') }
    finally { setBusy(false) }
  }
  const withdraw = async () => {
    setBusy(true); setError('')
    try { await api.deleteExclusionVote(memeId); setVote(null); setSaved(false) }
    catch (cause) { setError(cause.message || 'Oyun geri çekilemedi.') }
    finally { setBusy(false) }
  }

  return <div className="exclusion-box">
    {vote ? <>
      <div className="exclusion-status"><span className="exclusion-mark">✓</span><div><strong>{saved ? 'Oyun kaydedildi' : 'Bu meme için oyun var'}</strong><small>Bu meme kullanılmasın · {exclusionReasonName(vote.sebep)}{vote.not ? ` · “${vote.not}”` : ''}</small></div></div>
      {vote.karar === 'kalsin' && <p className="exclusion-decision">Ekip “kalsın” dedi. Oyunu yeniden kaydedersen meme tekrar havuza düşer.</p>}
      {vote.karar === 'cikarilsin' && <p className="exclusion-decision">Ekip bu meme'i kullanımdan çıkardı.</p>}
      <small>Oy etiketlemeyi durdurmaz; istersen bu işi ayrıca atlayabilirsin.</small>
      {vote.karar !== 'cikarilsin' && <div className="exclusion-actions"><button type="button" className="text-button" disabled={busy} onClick={openForm}>{vote.karar ? 'Yeniden oy ver' : 'Değiştir'}</button><button type="button" className="text-button danger-link" disabled={busy} onClick={withdraw}>Oyu geri çek</button></div>}
    </> : <>
      <div><strong>Bu meme veri setine girmemeli mi?</strong><small>Oyunu yalnızca sen ve admin görür. Meme havuza düşer ve ekipçe konuşulur.</small></div>
      <button type="button" className="button danger small exclusion-button" disabled={!loaded || busy} onClick={openForm}>⚑ Bu meme kullanılmasın</button>
    </>}
    {error && !open && <p className="field-error">{error}</p>}
    {open && createPortal(<div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false) }}><form className="modal" role="dialog" aria-modal="true" aria-labelledby="exclusion-title" onSubmit={saveVote}><button type="button" className="modal-close" aria-label="Kapat" onClick={() => setOpen(false)}>×</button><span className="eyebrow">KULLANILMASIN OYU · {memeId}</span><h2 id="exclusion-title">Bu meme neden kullanılmasın?</h2><p>Tek oy meme'i havuza düşürür; ekip havuzu toplantıda konuşur, admin kalsın ya da çıkarılsın der. Etiketleme kaldığı yerden sürer.</p><div className="reason-grid" role="radiogroup" aria-label="Sebep">{EXCLUSION_REASONS.map((item) => <label key={item.value} className={`radio-card ${reason === item.value ? 'active' : ''}`}><input type="radio" name="exclusion-reason" checked={reason === item.value} onChange={() => setReason(item.value)} /><span className="radio-dot" /><span>{item.label}</span></label>)}</div><label className="select-label">Not <span className="field-hint">İsteğe bağlı · {note.length}/{EXCLUSION_NOTE_MAX}</span><textarea rows="3" maxLength={EXCLUSION_NOTE_MAX} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Ör. m0412 ile aynı görsel" /></label>{error && <p className="field-error">{error}</p>}<div className="modal-actions"><button type="button" className="button secondary" onClick={() => setOpen(false)}>Vazgeç</button><button className="button primary" disabled={busy || !reason}>{busy ? 'Kaydediliyor…' : 'Oyu kaydet'}</button></div></form></div>, document.body)}
  </div>
}

function PoolThumb({ memeId, className = 'pool-thumb' }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let active = true
    let objectUrl = ''
    api.image(memeId, 'kucuk').then((blob) => { objectUrl = URL.createObjectURL(blob); if (active) setUrl(objectUrl); else URL.revokeObjectURL(objectUrl) }).catch(() => {})
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [memeId])
  return <div className={className}>{url ? <img src={url} alt={`${memeId} küçük görseli`} /> : <span>{memeId.slice(0, 1).toUpperCase()}</span>}</div>
}

/** Admin havuzu (ADR-0011): oylar, sebepler ve notlar açıkça görünür; karar admin'dedir. */
function ExclusionPool() {
  const [status, setStatus] = useState('bekliyor')
  const [items, setItems] = useState([])
  const [notes, setNotes] = useState({})
  const [loaded, setLoaded] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const refresh = useCallback(async () => {
    setError('')
    try { setItems(await api.exclusionPool(status)); setLoaded(true) }
    catch (cause) { setError(cause.message || 'Havuz yüklenemedi.') }
  }, [status])

  useEffect(() => { setLoaded(false); setItems([]); refresh() }, [refresh])

  const decide = async (memeId, karar) => {
    if (karar === 'cikarilsin' && !window.confirm(`${memeId} kullanımdan çıkarılsın mı? Kuyruklardan, atamalardan, incelemeden ve dışa aktarımdan düşer. “Kalsın” ile geri alınabilir.`)) return
    setBusyId(memeId); setError(''); setNotice('')
    try {
      await api.decideExclusion(memeId, { karar, not: (notes[memeId] || '').trim() || null })
      setNotes((old) => { const next = { ...old }; delete next[memeId]; return next })
      setNotice(karar === 'cikarilsin' ? `${memeId} kullanımdan çıkarıldı.` : status === 'cikarildi' ? `${memeId} geri alındı; yeniden kullanımda.` : `${memeId} kalıyor; havuzdan çıktı.`)
      await refresh()
    } catch (cause) { setError(cause.message || 'Karar kaydedilemedi.') }
    finally { setBusyId(null) }
  }

  const decisionText = (karar) => `${karar.karar === 'kalsin' ? 'Önceki karar: kalsın' : 'Çıkarılsın kararı'} · ${karar.karar_veren?.gorunen_ad || 'admin'} · ${formatDateTime(karar.zaman)}${karar.not ? ` — ${karar.not}` : ''}`

  return <div className="pool-page"><div className="page-heading"><div><div className="breadcrumbs">Yönetim <span>›</span> Kullanılmasın havuzu</div><h1>Kullanılmasın havuzu</h1><p>Etiketleme sırasında “Bu meme kullanılmasın” oyu alan meme'ler. Ekip konuştuktan sonra karar ver.</p></div><button className="text-button" onClick={refresh}>Yenile ↻</button></div>
    {error && <div className="toast error-banner">{error}<button onClick={() => setError('')}>×</button></div>}{notice && <div className="toast success-banner">{notice}<button onClick={() => setNotice('')}>×</button></div>}
    <div className="pool-tabs" role="tablist" aria-label="Havuz görünümü"><button role="tab" aria-selected={status === 'bekliyor'} className={status === 'bekliyor' ? 'active' : ''} onClick={() => setStatus('bekliyor')}>Karar bekleyenler</button><button role="tab" aria-selected={status === 'cikarildi'} className={status === 'cikarildi' ? 'active' : ''} onClick={() => setStatus('cikarildi')}>Çıkarılanlar</button></div>
    {!loaded ? (!error && <p className="muted tiny">Havuz yükleniyor…</p>) : items.length === 0 ? <div className="pool-empty"><strong>{status === 'bekliyor' ? 'Karar bekleyen meme yok' : 'Çıkarılan meme yok'}</strong><p>{status === 'bekliyor' ? 'Biri etiketlerken “Bu meme kullanılmasın” dediğinde meme burada görünür.' : '“Çıkarılsın” kararı verilen meme’ler burada listelenir.'}</p></div> : <div className="pool-list">{items.map((item) => <article className="pool-item" key={item.meme_id}><PoolThumb memeId={item.meme_id} /><div className="pool-body"><div className="pool-head"><strong>{item.meme_id}</strong><span className="badge private">{MEME_STATUS_NAMES[item.etiket_durumu] || item.etiket_durumu}</span><span className="pool-count">{item.oy_sayisi} oy</span></div><div className="pool-reasons">{item.sebepler.map((entry) => <span className="pool-chip" key={entry.sebep}>{exclusionReasonName(entry.sebep)} · {entry.sayi}</span>)}</div><ul className="pool-votes">{item.oylar.map((oy) => <li key={`${oy.takma_ad}-${oy.zaman}`}><strong>{oy.takma_ad}</strong><span>{exclusionReasonName(oy.sebep)}</span>{oy.not && <q>{oy.not}</q>}<time dateTime={oy.zaman}>{formatDateTime(oy.zaman)}</time></li>)}</ul>{item.son_karar && <p className="pool-last">{decisionText(item.son_karar)}</p>}<div className="pool-actions"><input aria-label={`${item.meme_id} için karar notu`} value={notes[item.meme_id] || ''} maxLength={1000} onChange={(event) => setNotes((old) => ({ ...old, [item.meme_id]: event.target.value }))} placeholder="Karar notu (isteğe bağlı)" />{status === 'bekliyor' ? <><button className="button secondary small" disabled={busyId !== null} onClick={() => decide(item.meme_id, 'kalsin')}>Kalsın</button><button className="button danger small" disabled={busyId !== null} onClick={() => decide(item.meme_id, 'cikarilsin')}>Çıkarılsın</button></> : <button className="button secondary small" disabled={busyId !== null} onClick={() => decide(item.meme_id, 'kalsin')}>Kalsın · kararı geri al</button>}</div></div></article>)}</div>}
  </div>
}

export default function App() {
  const [token, setAuth] = useState(getToken())
  const [user, setUser] = useState(null)
  const [view, setView] = useState('annotation')
  const [queue, setQueue] = useState([])
  const [progressStats, setProgressStats] = useState(null)
  const [current, setCurrent] = useState(null)
  const [annotation, setAnnotation] = useState(null)
  const [schema, setSchema] = useState(null)
  const [labels, setLabels] = useState({})
  const [content, setContent] = useState(blankContent())
  const [confidence, setConfidence] = useState({})
  const [familiarity, setFamiliarity] = useState(null)
  const [image, setImage] = useState('')
  const [zoomOpen, setZoomOpen] = useState(false)
  const [comments, setComments] = useState([])
  const [commentText, setCommentText] = useState('')
  const [commentType, setCommentType] = useState('soru')
  const [errors, setErrors] = useState([])
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  const [skipOpen, setSkipOpen] = useState(false)
  const [skipReason, setSkipReason] = useState('tanimiyorum')
  const [skipDescription, setSkipDescription] = useState('')
  const version = useRef(0)
  const contentRef = useRef(content)
  const dirty = useRef(false)
  const activeSeconds = useRef(0)
  const lastActivity = useRef(Date.now())
  const activeMemeId = useRef(null)

  useEffect(() => { contentRef.current = content }, [content])

  const loadWorkspace = useCallback(async () => {
    const me = await api.me()
    setUser(me)
    const [work, formSchema, labelList, stats] = await Promise.all([api.queue(), api.schema(), api.labels(), api.progressStats().catch(() => null)])
    setQueue(work); setSchema(formSchema); setLabels(labelList.alanlar || {}); setProgressStats(stats)
    const first = work.find((item) => ['atandi', 'devam_ediyor', 'revizyon_gerekli'].includes(item.durum_kodu))
    if (first && activeMemeId.current === null) await openAssignment(first)
  }, [])

  // Etiketlenirken havuz kararıyla çıkarılan meme kuyruktan düşer; otomatik kayıt da durur.
  const leaveExcluded = useCallback((annotationId) => {
    dirty.current = false; activeMemeId.current = null
    setQueue((old) => old.filter((item) => item.annotation_id !== annotationId))
    setCurrent(null); setAnnotation(null); setBusy(false)
    setError('Bu meme havuz kararıyla kullanımdan çıkarıldı; kuyruğundan kaldırıldı.')
  }, [])

  const openAssignment = useCallback(async (item) => {
    activeMemeId.current = item.meme_id
    activeSeconds.current = 0
    setBusy(true); setError(''); setNotice(''); setErrors([]); setComments([]); setCommentText(''); setCurrent(item); setAnnotation(null); setImage(''); setContent(blankContent()); setConfidence({}); setFamiliarity(null)
    try {
      let detail = await api.annotation(item.annotation_id)
      if (detail.durum_kodu === 'atandi') detail = await api.start(item.annotation_id)
      version.current = detail.surum || 1
      setAnnotation(detail)
      const loadedContent = { ...blankContent(), ...(detail.icerik || {}) }
      contentRef.current = loadedContent
      setContent(loadedContent)
      setConfidence(detail.alan_guveni || {})
      setFamiliarity(detail.tanidiklik ?? null)
      dirty.current = false
      const blob = await api.image(item.meme_id)
      const imageObjectUrl = URL.createObjectURL(blob)
      if (activeMemeId.current === item.meme_id) setImage(imageObjectUrl)
      else URL.revokeObjectURL(imageObjectUrl)
      api.memeComments(item.meme_id).then((result) => { if (activeMemeId.current === item.meme_id) setComments(result) }).catch(() => { if (activeMemeId.current === item.meme_id) setComments([]) })
    } catch (cause) {
      if (activeMemeId.current !== item.meme_id) return
      if (cause.code === 'MEME_CIKARILDI') leaveExcluded(item.annotation_id)
      else setError(cause.message || 'İş yüklenemedi.')
    } finally { if (activeMemeId.current === item.meme_id) setBusy(false) }
  }, [leaveExcluded])

  useEffect(() => { if (token) loadWorkspace().catch((cause) => { setError(cause.message); if (cause.status === 401) { clearToken(); setAuth(null) } }) }, [token, loadWorkspace])
  useEffect(() => () => { if (image) URL.revokeObjectURL(image) }, [image])

  useEffect(() => {
    const markActive = () => { lastActivity.current = Date.now() }
    window.addEventListener('pointerdown', markActive); window.addEventListener('keydown', markActive)
    const timer = window.setInterval(() => {
      if (view === 'annotation' && current && document.visibilityState === 'visible' && Date.now() - lastActivity.current < 10000) activeSeconds.current += 5
    }, 5000)
    return () => { window.removeEventListener('pointerdown', markActive); window.removeEventListener('keydown', markActive); window.clearInterval(timer) }
  }, [view, current])

  const save = useCallback(async (quiet = false) => {
    if (!current || !annotation || !dirty.current) return
    try {
      const result = await api.saveDraft(current.annotation_id, { surum: version.current, icerik: contentRef.current, ...(familiarity !== null ? { tanidiklik: familiarity } : {}), alan_guveni: confidence, aktif_sure_artis_sn: Math.min(activeSeconds.current, 300) })
      version.current = result.surum; activeSeconds.current = 0; dirty.current = false; setSavedAt(new Date())
      if (!quiet) setNotice('Taslağın kaydedildi.')
      return true
    } catch (cause) {
      if (cause.code === 'MEME_CIKARILDI') { leaveExcluded(current.annotation_id); return true }
      if (cause.code === 'SURUM_CAKISMASI') setError('Bu etiketleme başka bir sekmede açık. Değişikliklerini kaydetmeden önce sekmeleri kontrol et.')
      else setError(cause.message || 'Taslak kaydedilemedi.')
      return false
    }
  }, [current, annotation, familiarity, confidence, leaveExcluded])

  const switchAssignment = useCallback(async (item) => {
    if (dirty.current && !(await save(true))) return
    await openAssignment(item)
  }, [save, openAssignment])

  useEffect(() => {
    if (!current || !annotation) return undefined
    const timer = window.setInterval(() => save(true), 5000)
    const onLeave = () => { if (!dirty.current) return; api.saveDraft(current.annotation_id, { surum: version.current, icerik: contentRef.current, ...(familiarity !== null ? { tanidiklik: familiarity } : {}), alan_guveni: confidence, aktif_sure_artis_sn: Math.min(activeSeconds.current, 300) }, true).catch(() => {}) }
    window.addEventListener('beforeunload', onLeave)
    return () => { window.clearInterval(timer); window.removeEventListener('beforeunload', onLeave) }
  }, [current, annotation, save, familiarity, confidence])

  const update = (key, value) => { setContent((previous) => { const next = { ...previous, [key]: value }; contentRef.current = next; return next }); dirty.current = true; setErrors([]); setNotice(''); setError('') }
  const updateConfidence = (key, value) => { setConfidence((previous) => { const next = { ...previous }; if (value === null) delete next[key]; else next[key] = value; return next }); dirty.current = true; setErrors([]); setError('') }
  const completeCount = useMemo(() => Object.values(content).filter((value) => Array.isArray(value) ? value.length > 0 : value !== null && String(value).trim()).length, [content])
  const rules = schema?.alanlar || {}
  const orderedFields = Object.keys(rules).length ? Object.keys(rules).filter((key) => key in content) : Object.keys(content)

  const doLogin = async (username, password) => {
    setBusy(true); setError('')
    try { const result = await api.login(username, password); setToken(result.erisim_token); setAuth(result.erisim_token) }
    catch (cause) { setError(cause.message || 'Giriş yapılamadı.') }
    finally { setBusy(false) }
  }

  const doRegister = async (username, password) => {
    setBusy(true); setError('')
    try { const result = await api.register(username, password); setToken(result.erisim_token); setAuth(result.erisim_token) }
    catch (cause) { setError(cause.message || 'Üyelik oluşturulamadı.') }
    finally { setBusy(false) }
  }

  const submit = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      if (familiarity !== null && familiarity <= 2) { setError('Tanıdıklık puanın 1 veya 2 ise gönderemezsin. Bu işi “Meme aşinalığım düşük” gerekçesiyle atla; sıradaki kişiye otomatik gider.'); setSkipReason('tanidiklik_dusuk'); setSkipOpen(true); return }
      if (dirty.current && !(await save(true))) return
      if (activeMemeId.current === null) return
      const localErrors = validateAnnotationLocally(contentRef.current, schema, labels)
      if (localErrors.length) { setErrors(localErrors); setError('Göndermeden önce işaretli alanları tamamla.'); document.querySelector('.has-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); return }
      const validation = await api.validate(current.annotation_id)
      if (!validation.gecerli) { setErrors(validation.hatalar || []); setError('Göndermeden önce işaretli alanları tamamla.'); document.querySelector('.has-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); return }
      const result = await api.submit(current.annotation_id, version.current)
      setAnnotation(result); setNotice('Etiketin başarıyla gönderildi.'); dirty.current = false
      const next = queue.find((item) => item.annotation_id !== current.annotation_id && ['atandi', 'devam_ediyor', 'revizyon_gerekli'].includes(item.durum_kodu))
      if (next) { setQueue((old) => old.filter((item) => item.annotation_id !== current.annotation_id)); await openAssignment(next) }
      else { setCurrent(null); setAnnotation(null); activeMemeId.current = null; setQueue((old) => old.filter((item) => item.annotation_id !== current.annotation_id)) }
    } catch (cause) {
      if (cause.code === 'MEME_CIKARILDI') { leaveExcluded(current.annotation_id); return }
      setErrors(cause.fields || []); setError(cause.message || 'Etiket gönderilemedi.')
    }
    finally { setBusy(false) }
  }

  const doSkip = async () => {
    setBusy(true); setError('')
    try { await api.skip(current.annotation_id, { gerekce: skipReason, aciklama: skipDescription || null, ...(familiarity !== null ? { tanidiklik: familiarity } : {}) }); dirty.current = false; setQueue((old) => old.filter((item) => item.annotation_id !== current.annotation_id)); setCurrent(null); setAnnotation(null); activeMemeId.current = null; setSkipOpen(false); setNotice('İş atlandı ve yeniden atama kuyruğuna alındı.') }
    catch (cause) { setError(cause.message || 'İş atlanamadı.') }
    finally { setBusy(false) }
  }

  const logout = async () => {
    if (dirty.current && !(await save(true))) return
    clearToken(); setAuth(null); setUser(null); setCurrent(null); setAnnotation(null); activeMemeId.current = null
  }

  const addComment = async (event) => {
    event.preventDefault()
    if (!commentText.trim()) return
    try { const memeId = current.meme_id; const saved = await api.addMemeComment(memeId, { metin: commentText.trim(), tur: commentType }); if (activeMemeId.current === memeId) { setComments((old) => [...old, saved]); setCommentText('') } }
    catch (cause) { setError(cause.message || 'Yorum eklenemedi.') }
  }

  useEffect(() => {
    const onShortcut = (event) => {
      if (view !== 'annotation') return
      if (event.key.toLowerCase() === 's' && (event.metaKey || event.ctrlKey)) { event.preventDefault(); save(false) }
      if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) { event.preventDefault(); submit() }
      if (event.key === 'ArrowRight' && event.altKey && current) {
        event.preventDefault()
        const next = queue.find((item) => item.annotation_id !== current.annotation_id && ['atandi', 'devam_ediyor', 'revizyon_gerekli'].includes(item.durum_kodu))
        if (next) switchAssignment(next)
      }
    }
    window.addEventListener('keydown', onShortcut)
    return () => window.removeEventListener('keydown', onShortcut)
  }, [save, current, queue, switchAssignment, submit, view])

  const personalProgress = progressStats?.kullanicilar?.find((entry) => entry.kullanici?.id === user?.id)
  const assignedCount = personalProgress?.atanan ?? queue.length
  const completedCount = personalProgress?.tamamlanan ?? 0
  const progressPercent = assignedCount ? Math.min(100, Math.round((completedCount / assignedCount) * 100)) : 0

  if (!token) return <Login onLogin={doLogin} onRegister={doRegister} error={error} busy={busy} />
  return <div className="app-shell"><header className="topbar"><Brand /><nav className="topnav"><button className={view === 'annotation' ? 'nav-active' : ''} onClick={() => setView('annotation')}>Etiketleme</button><button className={view === 'queries' ? 'nav-active' : ''} onClick={() => setView('queries')}>Test sorguları</button>{user?.admin && <button className={view === 'pool' ? 'nav-active' : ''} onClick={() => setView('pool')}>Havuz</button>}</nav><div className="profile"><div className="avatar">{user?.gorunen_ad?.slice(0, 1) || 'A'}</div><span>{user?.gorunen_ad || 'Annotator'}</span><button className="icon-button" title="Çıkış yap" onClick={logout}>↗</button></div></header>
    <main className="workspace"><aside className="sidebar"><div className="side-heading"><div><p className="eyebrow">ÇALIŞMA ALANI</p><h2>Etiketleme</h2></div><span className="queue-count">{queue.length}</span></div><div className="progress-card"><div className="progress-meta"><span>İlerleme</span><strong>{completedCount} / {assignedCount}</strong></div><div className="progress-track"><span style={{ width: `${progressPercent}%` }} /></div><small>{personalProgress ? `${personalProgress.kalan} kalan · ${personalProgress.atlanan} atlanan` : 'İlerleme verisi yüklenemedi.'}</small></div><div className="queue-title"><span>SIRADAKİ İŞLER</span><button className="text-button" onClick={() => loadWorkspace().catch((cause) => setError(cause.message))}>Yenile ↻</button></div><div className="queue-list">{queue.map((item) => <button key={item.annotation_id} className={`queue-item ${current?.annotation_id === item.annotation_id ? 'active' : ''}`} onClick={() => switchAssignment(item)}><span className="queue-thumb" aria-hidden="true"><span>{item.meme_id.slice(0, 1).toUpperCase()}</span></span><span className="queue-info"><strong>{item.meme_id}</strong><small>{item.durum_kodu === 'revizyon_gerekli' ? 'Revizyon gerekli' : item.durum_kodu === 'devam_ediyor' ? 'Devam ediyor' : 'Etiketleme bekliyor'}</small>{item.kalibrasyon && <em>Kalibrasyon</em>}</span><span className="queue-arrow">›</span></button>)}{queue.length === 0 && <p className="empty-queue">Kuyruğunda bekleyen iş yok.</p>}</div><div className="privacy-note"><span>◉</span><p><strong>Kör etiketleme açık</strong><br />Diğer etiketleyicilerin yanıtları gizli tutulur.</p></div></aside>
      <section className="main-panel">{error && <div className="toast error-banner">{error}<button onClick={() => setError('')}>×</button></div>}{notice && <div className="toast success-banner">{notice}<button onClick={() => setNotice('')}>×</button></div>}
        {view === 'queries' ? <TestQueries user={user} /> : view === 'pool' && user?.admin ? <ExclusionPool /> : current && annotation ? <><div className="page-heading"><div><div className="breadcrumbs">Çalışma alanı <span>›</span> Etiketleme <span>›</span> <strong>{current.meme_id}</strong></div><h1>Meme'i etiketle</h1><p>Görseli incele ve aşağıdaki alanları kendi yorumuna göre doldur.</p></div><div className="heading-badges">{current.cift_etiket && <span className="badge private">◉ Kör etiketleme</span>}{current.kalibrasyon && <span className="badge calibration">✦ Kalibrasyon turu</span>}</div></div>
          <div className="label-layout"><section className="image-card"><div className="image-card-head"><div><span className="eyebrow">MEME GÖRSELİ</span><strong>{current.meme_id}</strong></div><button className="icon-button" title="Görseli büyüt" onClick={() => setZoomOpen(true)}>⌕</button></div><button type="button" className="meme-image" onClick={() => setZoomOpen(true)} aria-label="Görseli büyüt">{image ? <img src={image} alt={`Etiketlenecek meme: ${current.meme_id}`} /> : <div className="image-loading">Görsel yükleniyor…</div>}</button><div className="image-caption"><span className="image-dot" />Büyütmek için görsele tıkla</div><div className="image-stats"><div><span>ETİKETLEME</span><strong>{current.cift_etiket ? 'Çift etiket' : 'Tek etiket'}</strong></div><div><span>DURUM</span><strong>{annotation.durum_kodu === 'revizyon_gerekli' ? 'Revizyon' : 'Devam ediyor'}</strong></div></div><ExclusionVote key={current.meme_id} memeId={current.meme_id} /></section>
            <section className="form-card"><div className="form-top"><div><span className="eyebrow">ANNOTATION FORMU</span><h2>İçerik etiketleri</h2></div><span className="completion-pill">{completeCount} alan dolduruldu</span></div>{current.kalibrasyon && <div className="calibration-callout"><span>✦</span><div><strong>Kalibrasyon görevi</strong><p>Bu annotation kalibrasyon turuna aittir ve uyum ölçümüne katılmaz.</p></div></div>}{annotation.revizyon_notu && <div className="revision-callout"><strong>Revizyon notu</strong><p>{annotation.revizyon_notu}</p></div>}{annotation.on_doldurma === 'ai_taslagi' && <div className="draft-callout"><span>✎</span><div><strong>Form bir AI taslağıyla dolu geldi</strong><p>Her alanı kendi bilginle kontrol et ve düzelt. Taslak doğrudan gold olmaz; kurallara uymayan alanlar gönderirken işaretlenir.</p></div></div>}{annotation.on_doldurma === 'vlm_taslagi' && <div className="draft-callout"><span>✎</span><div><strong>Görsel tarif VLM taslağıyla dolu geldi</strong><p>Tarifi görsele bakarak kontrol et; anlam alanlarını sen doldur.</p></div></div>}<div className="familiarity-block"><div><strong>Meme'e tanıdıklık</strong><small>1–2 verirsen gönderemezsin; iş atlanır ve sıradaki kişiye gider. 3 verirsen ikinci bir kişi de etiketleyebilir.</small></div><select aria-label="Meme'e tanıdıklık puanı" value={familiarity ?? ''} onChange={(event) => { setFamiliarity(event.target.value ? Number(event.target.value) : null); dirty.current = true }}><option value="">Puan seç</option><option value="1">1 · Hiç görmedim</option><option value="2">2 · Gördüm, anlamını bilmiyorum</option><option value="3">3 · Anlamını biliyorum</option><option value="4">4 · Biliyorum, ara sıra kullanırım</option><option value="5">5 · Çok iyi tanıyorum</option></select></div><div className="blind-note"><span>◉</span><span><strong>Bağımsız değerlendir</strong><small>{current.cift_etiket ? 'Diğer annotator’ın etiketleri ve yorumları bu görev tamamlanana kadar gizlidir.' : 'Bu görevde başka annotator verisi gösterilmez.'}</small></span><span className="lock">KİLİTLİ</span></div>
              <div className="fields">{orderedFields.map((name) => <Field key={name} name={name} rule={rules[name] || {}} content={content} update={update} labels={labels} errors={errors} confidence={confidence} updateConfidence={updateConfidence} />)}</div>
              <section className="comments-panel"><div className="comments-heading"><div><strong>Yorumlar ve işaretler</strong><small>{current.cift_etiket ? 'Yorum görünürlüğü kör etiketleme kuralına göre sunucu tarafından filtrelenir.' : 'Bu meme hakkındaki ekip notları.'}</small></div><span>{comments.length}</span></div>{comments.filter((comment) => !current.cift_etiket || ['gonderildi', 'onaylandi'].includes(annotation.durum_kodu) || comment.yazan?.id === user?.id).map((comment) => <article className="comment-item" key={comment.id}><div><strong>{comment.yazan?.gorunen_ad}</strong><span>{comment.tur.replaceAll('_', ' ')}</span></div><p>{comment.metin}</p></article>)}<form className="comment-form" onSubmit={addComment}><select aria-label="Yorum türü" value={commentType} onChange={(event) => setCommentType(event.target.value)}><option value="soru">Soru</option><option value="kilavuz_onerisi">Kılavuz önerisi</option><option value="kopya_suphesi">Kopya şüphesi</option><option value="hata">Hata</option></select><input value={commentText} onChange={(event) => setCommentText(event.target.value)} placeholder="Ekip için not veya soru ekle…" /><button className="button secondary small" disabled={!commentText.trim()}>Ekle</button></form></section>
              <p className="keyboard-help">Kısayollar: Ctrl/Cmd + S kaydet · Ctrl/Cmd + Enter gönder · Alt + → sonraki iş</p><div className="form-actions"><button type="button" className="button secondary" onClick={() => { if (familiarity !== null && familiarity <= 2) setSkipReason('tanidiklik_dusuk'); setSkipOpen(true) }}>Bu işi atla</button><div className="action-right"><span className="save-state">{savedAt ? `Kaydedildi ${savedAt.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}` : dirty.current ? 'Kaydedilmemiş değişiklikler' : 'Otomatik kayıt açık'}</span><button type="button" className="button secondary" disabled={busy} onClick={() => save(false)}>Taslağı kaydet</button><button type="button" className="button primary" disabled={busy} onClick={submit}>{familiarity !== null && familiarity <= 2 ? 'Düşük tanıdıklık · Atla' : busy ? 'İşleniyor…' : 'Etiketi gönder'} <span>→</span></button></div></div>
            </section></div></> : queue.length ? <div className="empty-state"><div className="empty-illustration">→</div><h1>Sıradaki işe geç</h1><p>Kuyruğunda {queue.length} iş var. Soldaki listeden birini seç ya da sıradakini aç.</p><button className="button primary" disabled={busy} onClick={() => switchAssignment(queue[0])}>Sıradaki işi aç <span>→</span></button></div> : <div className="empty-state"><div className="empty-illustration">✓</div><h1>Hepsi tamamlandı</h1><p>Şu anda etiketlenecek başka işin yok. Yeni görevler geldiğinde burada görünecek.</p><button className="button secondary" onClick={() => loadWorkspace().catch((cause) => setError(cause.message))}>Kuyruğu yenile ↻</button></div>}
      </section>
    </main>{skipOpen && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSkipOpen(false) }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="skip-title"><button className="modal-close" onClick={() => setSkipOpen(false)}>×</button><span className="eyebrow">İŞİ ATLA</span><h2 id="skip-title">Bu meme'i neden atlıyorsun?</h2><p>Atlanan işler yeniden atama kuyruğuna alınır.</p><label className="select-label">Atlama nedeni<select value={skipReason} onChange={(event) => setSkipReason(event.target.value)}><option value="tanimiyorum">Meme'i tanımıyorum</option><option value="tanidiklik_dusuk">Meme aşinalığım düşük</option><option value="uygun_degil">Uygun değil</option><option value="diger">Diğer</option></select></label><label className="select-label">Açıklama <textarea rows="3" value={skipDescription} onChange={(event) => setSkipDescription(event.target.value)} placeholder="İsteğe bağlı kısa açıklama" /></label><div className="modal-actions"><button className="button secondary" onClick={() => setSkipOpen(false)}>Vazgeç</button><button className="button primary" disabled={busy} onClick={doSkip}>İşi atla</button></div></section></div>}</div>
}
