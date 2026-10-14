import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Play, Settings2, Square, VideoOff } from 'lucide-react'
import { Card, EmptyState, Loading, PageHeader, StatusBadge } from '../components/ui'
import LineEditor from '../components/LineEditor'
import DemoControls from '../components/DemoControls'
import { useToast } from '../components/Toast'
import { useTraffic } from '../components/TrafficProvider'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'
import { nf, typeColor } from '../utils/format'

export default function Live() {
  const toast = useToast()
  const { states, events } = useTraffic()
  const [sp, setSp] = useSearchParams()
  const cams = useApi('/cameras', { include_inactive: false })
  const [busy, setBusy] = useState(false)
  const [editor, setEditor] = useState(false)
  const [streamKey, setStreamKey] = useState(0)
  const [streamFailed, setStreamFailed] = useState(false)

  const list = cams.data || []
  const id = Number(sp.get('camera')) || list[0]?.id
  const cam = list.find((c) => c.id === id)
  const lines = useApi(`/cameras/${id}/lines`, null, { enabled: !!id })
  const zones = useApi(`/cameras/${id}/zones`, null, { enabled: !!id })
  const live = states[id]
  const running = live ? ['starting', 'running'].includes(live.status) : !!cam?.processing

  // refresh the camera list when the processor state changes (status badge, buttons)
  useEffect(() => { if (live) cams.reload() }, [live?.status]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setStreamFailed(false); setStreamKey((k) => k + 1) }, [id, running])

  const mine = useMemo(() => events.filter((e) => e.camera_id === id).slice(0, 12), [events, id])

  const start = async () => {
    setBusy(true)
    try { await api.post('/video/start', { camera_id: id }); toast.success('Processing started'); cams.reload() }
    catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  const stop = async () => {
    setBusy(true)
    try { await api.post('/video/stop', { camera_id: id }); toast.info('Stopping…') }
    catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }

  if (cams.loading && !cams.data) return <Loading height={300} />
  if (!list.length) return <EmptyState title="No active cameras" hint="Add a camera on the Cameras page first." />

  const progress = live?.total_frames ? Math.min(100, Math.round((live.frame_number / live.total_frames) * 100)) : null
  const dirs = Object.entries(live?.by_direction || {})
  const types = Object.entries(live?.by_type || {})

  return (
    <>
      <PageHeader title="Live monitoring" subtitle="Annotated feed from the AI pipeline: boxes, tracking IDs, counting lines and zones.">
        <select className="input !w-auto" value={id} onChange={(e) => setSp({ camera: e.target.value })} aria-label="Camera">
          {list.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <DemoControls compact />
        <button className="btn" onClick={() => setEditor(true)}><Settings2 size={15} /> Lines & zones</button>
        {running
          ? <button className="btn btn-danger" onClick={stop} disabled={busy}><Square size={15} /> Stop</button>
          : <button className="btn btn-primary" onClick={start} disabled={busy}><Play size={15} /> Start processing</button>}
      </PageHeader>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2 !p-3" title={cam?.name} right={<StatusBadge status={live?.status || cam?.status || 'offline'} />}>
          <div className="relative aspect-video overflow-hidden rounded-lg border border-line bg-black">
            {(running || live) && !streamFailed ? (
              <img key={streamKey} src={api.url(`/video/stream/${id}`) + `?k=${streamKey}`} alt="Processed video feed" className="h-full w-full object-contain" onError={() => setStreamFailed(true)} />
            ) : (
              <div className="grid h-full place-items-center text-center text-mute">
                <div><VideoOff className="mx-auto mb-2" size={28} /><p className="text-sm">{live?.status === 'error' ? live.message : 'Not processing. Press “Start processing” or “Start demo”.'}</p></div>
              </div>
            )}
            {live?.status === 'error' && <div className="absolute inset-x-0 bottom-0 bg-bad/90 px-3 py-2 text-sm text-white">{live.message}</div>}
          </div>
          {progress != null && (
            <div className="mt-3"><div className="h-1.5 overflow-hidden rounded-full bg-panel2"><div className="h-full bg-amber transition-all" style={{ width: `${progress}%` }} /></div>
              <div className="num mt-1 text-xs text-mute">Frame {nf(live.frame_number)} / {nf(live.total_frames)} · {progress}%</div></div>
          )}
          {live?.status === 'finished' && <p className="mt-2 text-sm text-ok">Video finished. All events are saved — see Analytics and Historical Data.</p>}
        </Card>

        <div className="space-y-4">
          <Card title="Current count">
            <div className="num text-5xl font-semibold text-amber">{nf(live?.total_count ?? 0)}</div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {types.length === 0 && <p className="col-span-2 text-xs text-mute">No vehicle has crossed a line yet in this run.</p>}
              {types.map(([t, n]) => (
                <div key={t} className="flex items-center justify-between rounded-lg border border-line bg-panel2 px-3 py-1.5 text-sm"><span className="flex items-center gap-2 capitalize"><span className="h-2 w-2 rounded-full" style={{ background: typeColor(t) }} />{t}</span><b className="num">{n}</b></div>
              ))}
            </div>
            {dirs.length > 0 && <div className="mt-3 space-y-1 text-sm">{dirs.map(([d, n]) => <div key={d} className="flex justify-between"><span className="capitalize text-mute">{d}</span><b className="num">{n}</b></div>)}</div>}
          </Card>
          <Card title="Pipeline">
            <dl className="num grid grid-cols-2 gap-y-1.5 text-sm">
              <dt className="text-mute">Processing FPS</dt><dd className="text-right">{live?.fps ?? '–'}</dd>
              <dt className="text-mute">Source FPS</dt><dd className="text-right">{live?.source_fps ? Math.round(live.source_fps) : '–'}</dd>
              <dt className="text-mute">Tracked now</dt><dd className="text-right">{live?.active_tracks ?? '–'}</dd>
              <dt className="text-mute">In zones</dt><dd className="text-right">{live ? Object.values(live.zone_occupancy || {}).reduce((a, b) => a + b, 0) : '–'}</dd>
            </dl>
          </Card>
          <Card title="Recent crossings">
            <div className="space-y-1.5">
              {mine.length === 0 && <p className="text-xs text-mute">Nothing yet.</p>}
              {mine.map((e) => (
                <div key={e.id} className="flex items-center justify-between text-sm animate-slideIn">
                  <span><b className="capitalize" style={{ color: typeColor(e.vehicle_type) }}>{e.vehicle_type}</b> <span className="num text-xs text-mute">#{e.track_id}</span></span>
                  <span className="text-xs text-mute">{e.direction} · {new Date(e.timestamp).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {editor && cam && <LineEditor camera={cam} lines={lines.data || []} zones={zones.data || []} running={running}
        onClose={() => setEditor(false)} onChanged={() => { lines.reload(); zones.reload() }} />}
    </>
  )
}
