import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, RotateCcw } from 'lucide-react'
import { api } from '../services/api'
import { useToast } from './Toast'
import { useTraffic } from './TrafficProvider'

export default function DemoControls({ compact }) {
  const toast = useToast(); const nav = useNavigate(); const { bump } = useTraffic()
  const [busy, setBusy] = useState(false)
  const start = async () => {
    setBusy(true)
    try {
      const r = await api.post('/demo/start')
      toast.success(r.status === 'already_running' ? 'Demo is already running.' : `Demo started with "${r.video}".`)
      nav(`/live?camera=${r.camera_id}`)
    } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  const reset = async () => {
    if (!window.confirm('Delete all stored traffic data of the demo camera?')) return
    try { const r = await api.post('/demo/reset'); toast.success(`Cleared ${r.deleted_events} demo events.`); bump() } catch (e) { toast.error(e.message) }
  }
  return (
    <>
      <button className="btn btn-primary" onClick={start} disabled={busy}><Play size={15} /> Start demo</button>
      {!compact && <button className="btn" onClick={reset}><RotateCcw size={15} /> Reset demo data</button>}
    </>
  )
}
