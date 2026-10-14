import { useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { Async, Card, Field, LevelBadge, Modal, PageHeader } from '../components/ui'
import TrafficMap from '../components/TrafficMap'
import { useToast } from '../components/Toast'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'
import { nf } from '../utils/format'

function AreaForm({ initial, onClose, onSaved }) {
  const toast = useToast()
  const [f, setF] = useState({ name: '', description: '', latitude: '', longitude: '', hourly_capacity: 1200, ...(initial || {}), description: initial?.description ?? '', latitude: initial?.latitude ?? '', longitude: initial?.longitude ?? '' })
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault(); setBusy(true)
    const body = { name: f.name, description: f.description || null, latitude: f.latitude === '' ? null : Number(f.latitude), longitude: f.longitude === '' ? null : Number(f.longitude), hourly_capacity: Number(f.hourly_capacity) }
    try { if (initial) await api.put(`/areas/${initial.id}`, body); else await api.post('/areas', body); toast.success('Area saved'); onSaved(); onClose() }
    catch (err) { toast.error(err.message) } finally { setBusy(false) }
  }
  return (
    <Modal title={initial ? 'Edit area' : 'Add area'} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Name"><input required className="input" value={f.name} onChange={set('name')} maxLength={120} /></Field>
        <Field label="Description"><input className="input" value={f.description} onChange={set('description')} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Latitude"><input type="number" step="any" min="-90" max="90" className="input" value={f.latitude} onChange={set('latitude')} /></Field>
          <Field label="Longitude"><input type="number" step="any" min="-180" max="180" className="input" value={f.longitude} onChange={set('longitude')} /></Field>
        </div>
        <Field label="Hourly capacity (vehicles/hour)" hint="Used to grade traffic as LOW / MODERATE / HIGH / CRITICAL (below 40% / 70% / 90% / above)."><input required type="number" min="1" max="100000" className="input" value={f.hourly_capacity} onChange={set('hourly_capacity')} /></Field>
        <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={busy}>Save</button></div>
      </form>
    </Modal>
  )
}

export default function Areas() {
  const toast = useToast()
  const areas = useApi('/areas')
  const stats = useApi('/traffic/by-area', null, { live: true })
  const map = useApi('/traffic/map', null, { live: true })
  const [form, setForm] = useState(null)
  const totals = Object.fromEntries((stats.data || []).map((a) => [a.area_id, a]))

  const remove = async (a) => {
    if (!window.confirm(`Delete area "${a.name}"? Cameras keep working but become unassigned.`)) return
    try { await api.del(`/areas/${a.id}`); toast.success('Area deleted'); areas.reload(); stats.reload() } catch (e) { toast.error(e.message) }
  }
  const levelOf = (id) => {
    const cs = (map.data || []).filter((c) => c.area_id === id)
    const order = ['NO_DATA', 'LOW', 'MODERATE', 'HIGH', 'CRITICAL']
    return cs.reduce((m, c) => (order.indexOf(c.traffic_level) > order.indexOf(m) ? c.traffic_level : m), 'NO_DATA')
  }

  return (
    <>
      <PageHeader title="Areas" subtitle="Group cameras into monitored areas and compare them.">
        <button className="btn btn-primary" onClick={() => setForm('new')}><Plus size={15} /> Add area</button>
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="All areas">
          <Async state={areas} emptyHint="Create an area to group cameras.">
            {(d) => (
              <div className="space-y-2">
                {d.map((a) => (
                  <div key={a.id} className="flex items-center justify-between gap-3 rounded-lg border border-line bg-panel2 p-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2"><span className="font-medium">{a.name}</span><LevelBadge level={levelOf(a.id)} /></div>
                      <div className="text-xs text-mute">{a.description || '—'} · capacity {nf(a.hourly_capacity)}/h</div>
                      {totals[a.id] && <div className="num mt-1 text-xs">Total <b>{nf(totals[a.id].total)}</b> · {nf(totals[a.id].car)} cars · {nf(totals[a.id].motorcycle)} motorcycles · {nf(totals[a.id].bus)} buses · {nf(totals[a.id].truck)} trucks</div>}
                    </div>
                    <div className="flex gap-1.5"><button className="btn px-2.5" onClick={() => setForm(a)} aria-label="Edit"><Pencil size={15} /></button><button className="btn btn-danger px-2.5" onClick={() => remove(a)} aria-label="Delete"><Trash2 size={15} /></button></div>
                  </div>
                ))}
              </div>
            )}
          </Async>
        </Card>
        <Card title="Map"><Async state={map} height={420}>{(d) => <TrafficMap cameras={d} height={420} />}</Async></Card>
      </div>
      {form && <AreaForm initial={form === 'new' ? null : form} onClose={() => setForm(null)} onSaved={() => { areas.reload(); stats.reload() }} />}
    </>
  )
}
