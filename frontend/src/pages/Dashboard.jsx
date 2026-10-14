import { ArrowDownRight, ArrowUpRight, Bike, Bus, Car, Gauge, Truck } from 'lucide-react'
import { Async, Card, PageHeader, Stat } from '../components/ui'
import TrafficMap from '../components/TrafficMap'
import DemoControls from '../components/DemoControls'
import { useTraffic } from '../components/TrafficProvider'
import { useApi } from '../hooks/useApi'
import { AreaCompare, HourlyChart, TypeBar } from '../charts/charts'
import { fmtTime, nf, pct, typeColor } from '../utils/format'

export default function Dashboard() {
  const { events } = useTraffic()
  const today = useApi('/traffic/today', null, { live: true })
  const hourly = useApi('/traffic/hourly', null, { live: true })
  const types = useApi('/traffic/by-type', { start_date: new Date().toISOString().slice(0, 10) }, { live: true })
  const areas = useApi('/traffic/by-area', null, { live: true })
  const map = useApi('/traffic/map', null, { live: true })
  const t = today.data
  const ch = t?.change_vs_yesterday_pct

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Live vehicle counts from your cameras. Updates automatically as vehicles cross the counting lines."><DemoControls /></PageHeader>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat label="Total today" value={nf(t?.total ?? 0)} icon={Gauge}
          sub={ch == null ? 'No data for yesterday' : <span className={`inline-flex items-center gap-1 ${ch >= 0 ? 'text-ok' : 'text-bad'}`}>{ch >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{pct(ch)} vs yesterday</span>} />
        <Stat label="Cars" value={nf(t?.by_type.car ?? 0)} icon={Car} color={typeColor('car')} />
        <Stat label="Motorcycles" value={nf(t?.by_type.motorcycle ?? 0)} icon={Bike} color={typeColor('motorcycle')} />
        <Stat label="Buses" value={nf(t?.by_type.bus ?? 0)} icon={Bus} color={typeColor('bus')} />
        <Stat label="Trucks" value={nf(t?.by_type.truck ?? 0)} icon={Truck} color={typeColor('truck')} />
      </div>
      {today.error && <p className="mt-3 text-sm text-bad">{today.error}</p>}

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card title="Hourly traffic · today" className="xl:col-span-2">
          <Async state={hourly} empty={(d) => !d.some((h) => h.count)}>{(d) => <HourlyChart data={d} />}</Async>
        </Card>
        <Card title="Live event feed">
          <div className="max-h-[260px] space-y-1.5 overflow-auto pr-1">
            {events.length === 0 && <p className="py-8 text-center text-sm text-mute">Waiting for vehicles to cross a counting line…</p>}
            {events.map((e) => (
              <div key={e.id} className="flex items-center justify-between rounded-lg border border-line bg-panel2 px-3 py-1.5 text-sm animate-slideIn">
                <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: typeColor(e.vehicle_type) }} /><b className="capitalize">{e.vehicle_type}</b><span className="text-mute">{e.direction}</span></span>
                <span className="num text-xs text-mute">{new Date(e.timestamp).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Vehicle types · today"><Async state={types}>{(d) => <TypeBar data={d} />}</Async></Card>
        <Card title="Area comparison"><Async state={areas}>{(d) => <AreaCompare data={d} />}</Async></Card>
      </div>

      <Card title="Camera & area map" className="mt-4">
        <Async state={map} height={360}>{(d) => <TrafficMap cameras={d} />}</Async>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-mute">
          {[['LOW', '#34d399'], ['MODERATE', '#fbbf24'], ['HIGH', '#fb923c'], ['CRITICAL', '#f85757'], ['NO DATA', '#64748b']].map(([l, c]) => (
            <span key={l} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{l}</span>
          ))}
          <span className="ml-auto">Level = last 15 min rate vs. the area's hourly capacity. Last update {fmtTime(new Date().toISOString())}</span>
        </div>
      </Card>
    </>
  )
}
