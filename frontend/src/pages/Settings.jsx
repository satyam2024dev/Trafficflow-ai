import { CheckCircle2, XCircle } from 'lucide-react'
import { Async, Card, PageHeader } from '../components/ui'
import DemoControls from '../components/DemoControls'
import { useApi } from '../hooks/useApi'

const Row = ({ k, v, ok }) => (
  <div className="flex items-center justify-between border-t border-line py-2 text-sm first:border-0">
    <span className="text-mute">{k}</span>
    <span className="num flex items-center gap-2">{ok === true && <CheckCircle2 size={14} className="text-ok" />}{ok === false && <XCircle size={14} className="text-bad" />}{v}</span>
  </div>
)

export default function Settings({ theme, setTheme }) {
  const health = useApi('/health', null, { live: true })
  const videos = useApi('/video/files')
  return (
    <>
      <PageHeader title="Settings" subtitle="System status and configuration." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="System health">
          <Async state={health} empty={() => false}>{(h) => (
            <>
              <Row k="API" v="reachable" ok />
              <Row k="Database" v={h.database.message} ok={h.database.ok} />
              <Row k="YOLO model" v={h.model.ok ? h.model.path : h.model.message} ok={h.model.ok} />
              <Row k="Detection classes" v={h.model.classes.join(', ')} />
              <Row k="Confidence threshold" v={h.model.confidence_threshold} />
              <Row k="Tracker" v={h.model.tracker} />
              <Row k="Device" v={h.model.device} />
              <Row k="Processing cameras" v={h.processing_cameras.length ? h.processing_cameras.join(', ') : 'none'} />
              <Row k="Live clients" v={h.websocket_clients} />
            </>
          )}</Async>
        </Card>
        <div className="space-y-4">
          <Card title="Appearance">
            <div className="flex gap-2">{['dark', 'light'].map((t) => <button key={t} className={`btn capitalize ${theme === t ? 'btn-primary' : ''}`} onClick={() => setTheme(t)}>{t}</button>)}</div>
          </Card>
          <Card title="Demo tools"><div className="flex flex-wrap gap-2"><DemoControls /></div><p className="mt-2 text-xs text-mute">“Start demo” uses videos/demo.mp4 (or the first video in the folder). “Reset” clears only the demo camera's stored data.</p></Card>
          <Card title="Videos on the server">
            <Async state={videos} emptyHint="Copy traffic videos (.mp4, .avi, .mov, .mkv) into the /videos folder of the project.">
              {(d) => <ul className="space-y-1 text-sm">{d.map((v) => <li key={v.name} className="flex justify-between"><span>{v.name}</span><span className="num text-mute">{v.size_mb} MB</span></li>)}</ul>}
            </Async>
          </Card>
          <Card title="Changing AI settings"><p className="text-sm text-mute">Model, confidence threshold, tracker, frame skipping and resolution are set in the <code className="num">.env</code> file (see <code className="num">.env.example</code>) and applied after restarting the backend. They are deliberately not editable from the browser.</p></Card>
        </div>
      </div>
    </>
  )
}
