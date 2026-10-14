import { useState } from 'react'
import { Spline, Square, Trash2 } from 'lucide-react'
import { api } from '../services/api'
import { Field, Modal } from './ui'
import { useToast } from './Toast'

/** Draw counting lines / zones on a snapshot of the camera. Coordinates are saved normalised (0..1). */
export default function LineEditor({ camera, lines, zones, running, onClose, onChanged }) {
  const toast = useToast()
  const [mode, setMode] = useState('line')
  const [pts, setPts] = useState([])
  const [name, setName] = useState('')
  const [ab, setAb] = useState('northbound')
  const [ba, setBa] = useState('southbound')
  const [busy, setBusy] = useState(false)
  const [imgErr, setImgErr] = useState(null)

  const click = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const p = [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))]
    setPts((cur) => (mode === 'line' ? (cur.length >= 2 ? [p] : [...cur, p]) : [...cur, p]))
  }
  const ready = mode === 'line' ? pts.length === 2 : pts.length >= 3

  const save = async () => {
    setBusy(true)
    try {
      if (mode === 'line') {
        await api.post(`/cameras/${camera.id}/lines`, { name: name || 'Counting line', x1: pts[0][0], y1: pts[0][1], x2: pts[1][0], y2: pts[1][1], direction_ab: ab, direction_ba: ba })
      } else {
        await api.post(`/cameras/${camera.id}/zones`, { name: name || 'Zone', polygon: pts })
      }
      toast.success(running ? 'Saved. Stop and restart processing for it to take effect.' : 'Saved.')
      setPts([]); setName(''); onChanged()
    } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  const remove = async (kind, id) => {
    try { await api.del(`/${kind}/${id}`); onChanged() } catch (e) { toast.error(e.message) }
  }

  // arrow showing which way direction A is (towards the LEFT-hand side when walking point 1 -> point 2)
  let arrow = null
  if (mode === 'line' && pts.length === 2) {
    const [a, b] = pts, dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1
    const nx = dy / len, ny = -dx / len, mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2
    arrow = { x1: mx, y1: my, x2: mx + nx * 0.1, y2: my + ny * 0.1 }
  }

  return (
    <Modal title={`Counting lines & zones — ${camera.name}`} onClose={onClose} wide>
      <div className="mb-3 flex gap-2">
        <button className={`btn ${mode === 'line' ? 'btn-primary' : ''}`} onClick={() => { setMode('line'); setPts([]) }}><Spline size={15} /> Counting line</button>
        <button className={`btn ${mode === 'zone' ? 'btn-primary' : ''}`} onClick={() => { setMode('zone'); setPts([]) }}><Square size={15} /> Zone (polygon)</button>
      </div>
      <p className="mb-2 text-xs text-mute">
        {mode === 'line' ? 'Click two points on the image to place the line.' : 'Click three or more points to outline the zone.'}
        {' '}Existing items are shown in red (lines) and blue (zones).
      </p>
      <div className="relative overflow-hidden rounded-lg border border-line bg-black">
        {imgErr ? <p className="p-6 text-sm text-bad">{imgErr}</p> : (
          <>
            <img src={api.url(`/cameras/${camera.id}/snapshot`) + `?t=${Date.now()}`} alt="Camera snapshot" className="block w-full select-none"
              draggable={false} onError={() => setImgErr('No snapshot available. For video files, make sure the file exists in the /videos folder; for webcam/RTSP, start processing first.')} />
            <svg className="absolute inset-0 h-full w-full cursor-crosshair" viewBox="0 0 1 1" preserveAspectRatio="none" onClick={click}>
              {lines.map((l) => <line key={l.id} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="#f85757" strokeWidth="0.006" />)}
              {zones.map((z) => <polygon key={z.id} points={z.polygon.map((p) => p.join(',')).join(' ')} fill="#60a5fa33" stroke="#60a5fa" strokeWidth="0.004" />)}
              {mode === 'line' && pts.length === 2 && <line x1={pts[0][0]} y1={pts[0][1]} x2={pts[1][0]} y2={pts[1][1]} stroke="#ffb020" strokeWidth="0.007" />}
              {mode === 'zone' && pts.length > 1 && <polygon points={pts.map((p) => p.join(',')).join(' ')} fill="#ffb02033" stroke="#ffb020" strokeWidth="0.005" />}
              {arrow && <line {...arrow} stroke="#34d399" strokeWidth="0.006" />}
              {pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r="0.008" fill="#ffb020" />)}
            </svg>
          </>
        )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Field label="Name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder={mode === 'line' ? 'e.g. Northern exit' : 'e.g. Junction box'} maxLength={120} /></Field>
        {mode === 'line' && (
          <>
            <Field label="Label A (green arrow side)" hint="Vehicles crossing towards the green arrow."><input className="input" value={ab} onChange={(e) => setAb(e.target.value)} maxLength={40} /></Field>
            <Field label="Label B (opposite)"><input className="input" value={ba} onChange={(e) => setBa(e.target.value)} maxLength={40} /></Field>
          </>
        )}
      </div>
      <div className="mt-3 flex gap-2">
        <button className="btn btn-primary" disabled={!ready || busy || !ab || !ba} onClick={save}>Save {mode}</button>
        <button className="btn" onClick={() => setPts([])} disabled={!pts.length}>Clear points</button>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {[['Lines', 'lines', lines], ['Zones', 'zones', zones]].map(([t, kind, items]) => (
          <div key={kind}>
            <div className="label">{t} ({items.length})</div>
            {items.length === 0 && <p className="text-xs text-mute">None yet.</p>}
            {items.map((i) => (
              <div key={i.id} className="mb-1 flex items-center justify-between rounded-lg border border-line px-3 py-1.5 text-sm">
                <span>{i.name}{kind === 'lines' && <span className="ml-2 text-xs text-mute">{i.direction_ab} / {i.direction_ba}</span>}</span>
                <button className="text-mute hover:text-bad" onClick={() => remove(kind === 'lines' ? 'lines' : 'zones', i.id)} aria-label={`Delete ${i.name}`}><Trash2 size={15} /></button>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Modal>
  )
}
