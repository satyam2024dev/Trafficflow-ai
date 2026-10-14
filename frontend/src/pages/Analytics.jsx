import { useState } from 'react'
import { TrendingDown, TrendingUp, Minus } from 'lucide-react'
import { Async, Card, LevelBadge, PageHeader, Stat } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { AreaCompare, DirectionPie, HourlyChart, PeakChart, TrendLine, TypeBar } from '../charts/charts'
import { daysAgo, nf, pct } from '../utils/format'

function Prediction({ areaId }) {
  const p = useApi('/predictions', { area_id: areaId, hours: 6 }, { live: true })
  return (
    <Card title="Traffic prediction (next 6 hours)" right={<span className="rounded border border-amber/50 bg-amber/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-amber">Prediction</span>}>
      <Async state={p} empty={() => false}>
        {(d) => d.status !== 'ok' ? (
          <p className="py-6 text-sm text-mute">{d.message}</p>
        ) : (
          <>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {d.predictions.map((x) => (
                <div key={x.hour_start} className="rounded-lg border border-line bg-panel2 p-3">
                  <div className="flex items-center justify-between"><span className="num text-sm font-medium">{x.label}</span><LevelBadge level={x.traffic_status} /></div>
                  <div className="num mt-1 text-xl font-semibold">≈ {nf(x.predicted_vehicles)}</div>
                  <div className="mt-1 text-[11px] text-mute">{x.confidence} confidence · {x.basis}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-mute">{d.disclaimer} Based on {d.history_hours} recorded hour(s) over {d.history_days} day(s); capacity {nf(d.hourly_capacity)}/h for {d.scope}.</p>
          </>
        )}
      </Async>
    </Card>
  )
}

export default function Analytics() {
  const [area, setArea] = useState('')
  const [camera, setCamera] = useState('')
  const [days, setDays] = useState(14)
  const areas = useApi('/areas'); const cams = useApi('/cameras')
  const f = { area_id: area, camera_id: camera }
  const range = { ...f, start_date: daysAgo(days - 1) }
  const hourly = useApi('/traffic/hourly', { ...f, hours: 24 }, { live: true })
  const daily = useApi('/traffic/daily', { ...f, days }, { live: true })
  const weekly = useApi('/traffic/weekly', f, { live: true })
  const monthly = useApi('/traffic/monthly', f, { live: true })
  const types = useApi('/traffic/by-type', range, { live: true })
  const dirs = useApi('/traffic/by-direction', range, { live: true })
  const byArea = useApi('/traffic/by-area', range, { live: true })
  const byCam = useApi('/traffic/by-camera', range, { live: true })
  const peaks = useApi('/traffic/peak-hours', f, { live: true })
  const trend = useApi('/traffic/trends', f, { live: true })
  const t = trend.data
  const TI = t?.direction === 'up' ? TrendingUp : t?.direction === 'down' ? TrendingDown : Minus

  return (
    <>
      <PageHeader title="Traffic analytics" subtitle="Every chart below is computed from the PostgreSQL database.">
        <select className="input !w-auto" value={area} onChange={(e) => setArea(e.target.value)} aria-label="Area"><option value="">All areas</option>{(areas.data || []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select>
        <select className="input !w-auto" value={camera} onChange={(e) => setCamera(e.target.value)} aria-label="Camera"><option value="">All cameras</option>{(cams.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select className="input !w-auto" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Range">{[7, 14, 30, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}</select>
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Last 7 days" value={nf(t?.last_7_days ?? 0)} />
        <Stat label="Previous 7 days" value={nf(t?.previous_7_days ?? 0)} />
        <Stat label="Weekly trend" icon={TI} value={t?.change_pct == null ? 'n/a' : pct(t.change_pct)} sub={t?.direction === 'no_baseline' ? 'Needs a previous week of data' : t?.direction} color={t?.direction === 'down' ? '#f85757' : '#34d399'} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card title="Hourly traffic · last 24 h"><Async state={hourly} empty={(d) => !d.some((h) => h.count)}>{(d) => <HourlyChart data={d} />}</Async></Card>
        <Card title={`Daily trend · last ${days} days`}><Async state={daily} empty={(d) => !d.some((x) => x.count)}>{(d) => <TrendLine data={d} />}</Async></Card>
        <Card title="Vehicle type distribution"><Async state={types}>{(d) => <TypeBar data={d} />}</Async></Card>
        <Card title="Direction-wise traffic"><Async state={dirs}>{(d) => <DirectionPie data={d} />}</Async></Card>
        <Card title="Area comparison"><Async state={byArea}>{(d) => <AreaCompare data={d} />}</Async></Card>
        <Card title="Peak hours · average vehicles per day">
          <Async state={peaks} empty={(d) => !d.peak_hours.length}>{(d) => (
            <>
              <PeakChart data={d.hours} />
              <p className="mt-2 text-xs text-mute">Busiest: {d.peak_hours.map((h) => `${h.label} (≈${h.avg_per_day}/day)`).join(', ')}</p>
            </>
          )}</Async>
        </Card>
        <Card title="Weekly traffic"><Async state={weekly} empty={(d) => !d.some((x) => x.count)}>{(d) => <TrendLine data={d} />}</Async></Card>
        <Card title="Monthly traffic"><Async state={monthly} empty={(d) => !d.some((x) => x.count)}>{(d) => <TrendLine data={d} />}</Async></Card>
      </div>

      <Card title="Camera-wise traffic" className="mt-4">
        <Async state={byCam}>{(d) => (
          <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-xs uppercase tracking-wider text-mute"><tr>{['Camera', 'Area', 'Cars', 'Motorcycles', 'Buses', 'Trucks', 'Total'].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody>{d.map((c) => <tr key={c.camera_id} className="border-t border-line"><td className="px-3 py-2 font-medium">{c.camera_name}</td><td className="px-3 py-2">{c.area_name || '—'}</td>{['car', 'motorcycle', 'bus', 'truck'].map((k) => <td key={k} className="num px-3 py-2">{nf(c[k])}</td>)}<td className="num px-3 py-2 font-semibold">{nf(c.total)}</td></tr>)}</tbody></table></div>
        )}</Async>
      </Card>

      <div className="mt-4"><Prediction areaId={area} /></div>
    </>
  )
}
