import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Pencil, Plus, Power, Radio, Trash2 } from 'lucide-react'
import { Async, Card, Field, Modal, PageHeader, StatusBadge } from '../components/ui'
import { useToast } from '../components/Toast'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'

const EMPTY = { name: '', location: '', area_id: '', source_type: 'video_file', source_url: '', latitude: '', longitude: '' }

function CameraForm({ initial, areas, videos, onClose, onSaved }) {
  const toast = useToast()
  const [f, setF] = useState(initial ? { ...EMPTY, ...initial, area_id: initial.area_id ?? '', latitude: initial.latitude ?? '', longitude: initial.longitude ?? '', location: initial.location ?? '' } : EMPTY)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault(); setBusy(true)
    const body = { ...f, area_id: f.area_id === '' ? null : Number(f.area_id), latitude: f.latitude === '' ? null : Number(f.latitude), longitude: f.longitude === '' ? null : Number(f.longitude), location: f.location || null }
    try {
      if (initial) await api.put(`/cameras/${initial.id}`, body); else await api.post('/cameras', body)
      toast.success(initial ? 'Camera updated' : 'Camera added'); onSaved(); onClose()
    } catch (err) { toast.error(err.message) } finally { setBusy(false) }
  }
  return (
    <Modal title={initial ? 'Edit camera' : 'Add camera'} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Name"><input required className="input" value={f.name} onChange={set('name')} maxLength={120} /></Field>
        <Field label="Location"><input className="input" value={f.location} onChange={set('location')} placeholder="e.g. MG Road & 5th Cross" /></Field>
        <Field label="Area"><select className="input" value={f.area_id} onChange={set('area_id')}><option value="">— none —</option>{areas.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></Field>
        <Field label="Source type">
          <select className="input" value={f.source_type} onChange={(e) => setF({ ...f, source_type: e.target.value, source_url: '' })}>
            <option value="video_file">Video file (server /videos folder)</option>
            <option value="webcam">Webcam (experimental)</option>
            <option value="rtsp">RTSP / IP camera (experimental)</option>
          </select>
        </Field>
        {f.source_type === 'video_file' && (
          <Field label="Video file" hint="Only files placed in the server's /videos folder can be chosen.">
            <select required className="input" value={f.source_url} onChange={set('source_url')}>
              <option value="">Select a video…</option>
              {videos.map((v) => <option key={v.name} value={v.name}>{v.name} ({v.size_mb} MB)</option>)}
            </select>
          </Field>
        )}
        {f.source_type === 'webcam' && <Field label="Device index" hint="0 is usually the default webcam. Works when the backend runs on the machine with the camera."><input required className="input" value={f.source_url} onChange={set('source_url')} placeholder="0" /></Field>}
        {f.source_type === 'rtsp' && <Field label="RTSP URL" hint="Wired up but not production-tested. Credentials in the URL are stored in the database — use a read-only camera account."><input required className="input" value={f.source_url} onChange={set('source_url')} placeholder="rtsp://192.168.1.10:554/stream1" /></Field>}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Latitude"><input type="number" step="any" min="-90" max="90" className="input" value={f.latitude} onChange={set('latitude')} /></Field>
          <Field label="Longitude"><input type="number" step="any" min="-180" max="180" className="input" value={f.longitude} onChange={set('longitude')} /></Field>
        </div>
        <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={busy}>{initial ? 'Save changes' : 'Add camera'}</button></div>
      </form>
    </Modal>
  )
}

export default function Cameras() {
  const toast = useToast()
  const cams = useApi('/cameras', null, { live: true })
  const areas = useApi('/areas')
  const videos = useApi('/video/files')
  const [form, setForm] = useState(null) // null | 'new' | camera

  const toggle = async (c) => {
    try { await api.put(`/cameras/${c.id}`, { is_active: !c.is_active }); toast.success(c.is_active ? 'Camera deactivated' : 'Camera activated'); cams.reload() } catch (e) { toast.error(e.message) }
  }
  const remove = async (c) => {
    if (!window.confirm(`Permanently delete "${c.name}" AND all of its stored traffic events? This cannot be undone.\n\n(To keep history, use Deactivate instead.)`)) return
    try { await api.del(`/cameras/${c.id}`, { permanent: true }); toast.success('Camera deleted'); cams.reload() } catch (e) { toast.error(e.message) }
  }

  return (
    <>
      <PageHeader title="Cameras" subtitle="Each camera has its own source, area and counting lines.">
        <button className="btn btn-primary" onClick={() => setForm('new')}><Plus size={15} /> Add camera</button>
      </PageHeader>
      <Card>
        <Async state={cams} emptyHint="Add your first camera to begin.">
          {(d) => (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wider text-mute"><tr>{['Camera', 'Area', 'Source', 'Status', ''].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
                <tbody>
                  {d.map((c) => (
                    <tr key={c.id} className={`border-t border-line ${c.is_active ? '' : 'opacity-60'}`}>
                      <td className="px-3 py-3"><div className="font-medium">{c.name}</div><div className="text-xs text-mute">{c.location || '—'}</div></td>
                      <td className="px-3 py-3">{c.area_name || <span className="text-mute">—</span>}</td>
                      <td className="px-3 py-3"><span className="rounded border border-line px-1.5 py-0.5 text-xs">{c.source_type}</span> <span className="num text-xs text-mute">{c.source_type === 'rtsp' ? c.source_url.replace(/\/\/[^@/]*@/, '//***@') : c.source_url}</span></td>
                      <td className="px-3 py-3"><StatusBadge status={c.status} />{c.last_error && <div className="mt-1 max-w-xs text-xs text-bad">{c.last_error}</div>}</td>
                      <td className="px-3 py-3"><div className="flex justify-end gap-1.5">
                        <Link className="btn px-2.5" to={`/live?camera=${c.id}`} title="Open live view"><Radio size={15} /></Link>
                        <button className="btn px-2.5" onClick={() => setForm(c)} title="Edit"><Pencil size={15} /></button>
                        <button className="btn px-2.5" onClick={() => toggle(c)} title={c.is_active ? 'Deactivate' : 'Activate'}><Power size={15} /></button>
                        <button className="btn btn-danger px-2.5" onClick={() => remove(c)} title="Delete permanently"><Trash2 size={15} /></button>
                      </div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Async>
      </Card>
      {form && <CameraForm initial={form === 'new' ? null : form} areas={areas.data || []} videos={videos.data || []} onClose={() => setForm(null)} onSaved={cams.reload} />}
    </>
  )
}
