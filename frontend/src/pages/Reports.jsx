import { useState } from 'react'
import { Download, Printer } from 'lucide-react'
import { Async, Card, PageHeader, Stat } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'
import { daysAgo, isoDate, nf, typeColor } from '../utils/format'

export default function Reports() {
  const [f, setF] = useState({ start_date: daysAgo(6), end_date: isoDate(new Date()), area_id: '', camera_id: '' })
  const areas = useApi('/areas'); const cams = useApi('/cameras')
  const rep = useApi('/reports', f, { live: true })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <>
      <PageHeader title="Reports" subtitle="Generate a traffic report for any period, area or camera.">
        <a className="btn btn-primary" href={api.url('/reports', { ...f, format: 'csv' })} download><Download size={15} /> Download CSV</a>
        <button className="btn" onClick={() => window.print()}><Printer size={15} /> Print / Save as PDF</button>
      </PageHeader>
      <Card className="no-print">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div><span className="label">From</span><input type="date" className="input" value={f.start_date} max={f.end_date} onChange={set('start_date')} /></div>
          <div><span className="label">To</span><input type="date" className="input" value={f.end_date} min={f.start_date} onChange={set('end_date')} /></div>
          <div><span className="label">Area</span><select className="input" value={f.area_id} onChange={set('area_id')}><option value="">All areas</option>{(areas.data || []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
          <div><span className="label">Camera</span><select className="input" value={f.camera_id} onChange={set('camera_id')}><option value="">All cameras</option>{(cams.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        </div>
      </Card>
      <div className="mt-4">
        <Async state={rep} empty={() => false}>
          {(r) => (
            <div className="space-y-4">
              <Card title="Summary">
                <p className="text-sm">{r.summary}</p>
                <p className="mt-1 text-xs text-mute">Generated {new Date(r.generated_at).toLocaleString()} · Area: {r.area} · Camera: {r.camera}</p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Stat label="Total vehicles" value={nf(r.total_vehicles)} />{r.by_type.slice(0, 3).map((t) => <Stat key={t.vehicle_type} label={t.vehicle_type} value={nf(t.count)} sub={`${t.share_pct}% of traffic`} color={typeColor(t.vehicle_type)} />)}</div>
              </Card>
              <div className="grid gap-4 lg:grid-cols-2">
                <Card title="Peak hours (avg vehicles/day)">{r.peak_hours.length ? <ul className="space-y-1 text-sm">{r.peak_hours.map((h) => <li key={h.hour} className="flex justify-between"><span className="num">{h.label}</span><b className="num">≈ {h.avg_per_day}</b></li>)}</ul> : <p className="text-sm text-mute">No traffic in this range.</p>}</Card>
                <Card title="Direction">{r.by_direction.length ? <ul className="space-y-1 text-sm">{r.by_direction.map((d) => <li key={d.direction} className="flex justify-between"><span className="capitalize">{d.direction}</span><b className="num">{nf(d.count)}</b></li>)}</ul> : <p className="text-sm text-mute">No traffic in this range.</p>}</Card>
              </div>
              <Card title="Daily totals">
                <div className="max-h-72 overflow-auto"><table className="w-full text-left text-sm"><thead className="text-xs uppercase text-mute"><tr>{['Date', 'Total', 'Cars', 'Motorcycles', 'Buses', 'Trucks'].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
                  <tbody>{r.daily.map((d) => <tr key={d.bucket} className="border-t border-line"><td className="px-3 py-1.5">{d.label}</td><td className="num px-3 py-1.5 font-semibold">{nf(d.count)}</td><td className="num px-3 py-1.5">{d.car}</td><td className="num px-3 py-1.5">{d.motorcycle}</td><td className="num px-3 py-1.5">{d.bus}</td><td className="num px-3 py-1.5">{d.truck}</td></tr>)}</tbody></table></div>
              </Card>
            </div>
          )}
        </Async>
      </div>
    </>
  )
}
