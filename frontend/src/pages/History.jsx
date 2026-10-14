import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download, Search } from 'lucide-react'
import { Async, Card, PageHeader } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'
import { fmtTime, nf, typeColor, TYPES } from '../utils/format'

const COLS = [['timestamp', 'Time'], ['camera', 'Camera'], ['area', 'Area'], ['track_id', 'Track'], ['vehicle_type', 'Type'], ['direction', 'Direction'], ['confidence', 'Conf.']]

export default function History() {
  const [flt, setFlt] = useState({ start_date: '', end_date: '', area_id: '', camera_id: '', vehicle_type: '', direction: '' })
  const [q, setQ] = useState(''); const [search, setSearch] = useState('')
  const [sort, setSort] = useState({ by: 'timestamp', order: 'desc' })
  const [page, setPage] = useState(1); const [size, setSize] = useState(25)
  const areas = useApi('/areas'); const cams = useApi('/cameras'); const dirs = useApi('/traffic/by-direction')

  useEffect(() => { const t = setTimeout(() => { setSearch(q); setPage(1) }, 350); return () => clearTimeout(t) }, [q])
  const set = (k) => (e) => { setFlt({ ...flt, [k]: e.target.value }); setPage(1) }
  const params = { ...flt, search, page, page_size: size, sort_by: sort.by, order: sort.order }
  const ev = useApi('/events', params, { live: true })
  const total = ev.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / size))
  const exportParams = { ...flt, search }
  const toggleSort = (by) => setSort((s) => ({ by, order: s.by === by && s.order === 'desc' ? 'asc' : 'desc' }))

  return (
    <>
      <PageHeader title="Historical data" subtitle="Filter, search and export every stored counting event.">
        <a className="btn btn-primary" href={api.url('/events/export', exportParams)} download><Download size={15} /> Export CSV</a>
      </PageHeader>
      <Card>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          <div><span className="label">From</span><input type="date" className="input" value={flt.start_date} max={flt.end_date || undefined} onChange={set('start_date')} /></div>
          <div><span className="label">To</span><input type="date" className="input" value={flt.end_date} min={flt.start_date || undefined} onChange={set('end_date')} /></div>
          <div><span className="label">Area</span><select className="input" value={flt.area_id} onChange={set('area_id')}><option value="">All</option>{(areas.data || []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
          <div><span className="label">Camera</span><select className="input" value={flt.camera_id} onChange={set('camera_id')}><option value="">All</option>{(cams.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
          <div><span className="label">Vehicle type</span><select className="input" value={flt.vehicle_type} onChange={set('vehicle_type')}><option value="">All</option>{TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
          <div><span className="label">Direction</span><select className="input" value={flt.direction} onChange={set('direction')}><option value="">All</option>{(dirs.data || []).map((d) => <option key={d.direction} value={d.direction}>{d.direction}</option>)}</select></div>
          <div><span className="label">Search</span><div className="relative"><Search size={14} className="absolute left-3 top-3 text-mute" /><input className="input !pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder="type, camera, track…" maxLength={60} /></div></div>
        </div>
      </Card>

      <Card className="mt-4" title={`${nf(total)} event${total === 1 ? '' : 's'}`} right={<button className="text-xs text-mute underline hover:text-ink" onClick={() => { setFlt({ start_date: '', end_date: '', area_id: '', camera_id: '', vehicle_type: '', direction: '' }); setQ('') }}>Reset filters</button>}>
        <Async state={ev} empty={(d) => !d.items.length} emptyHint="No events match these filters. Run a video, or widen the filters.">
          {(d) => (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wider text-mute"><tr>
                  {COLS.map(([k, label]) => (
                    <th key={k} className="sortable px-3 py-2 font-medium" onClick={() => toggleSort(k)} aria-sort={sort.by === k ? (sort.order === 'asc' ? 'ascending' : 'descending') : 'none'}>
                      <span className="inline-flex items-center gap-1">{label}{sort.by === k && (sort.order === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}</span>
                    </th>
                  ))}
                </tr></thead>
                <tbody>
                  {d.items.map((e) => (
                    <tr key={e.id} className="border-t border-line hover:bg-panel2">
                      <td className="num px-3 py-2 text-xs">{fmtTime(e.timestamp)}</td><td className="px-3 py-2">{e.camera_name}</td><td className="px-3 py-2">{e.area_name || '—'}</td>
                      <td className="num px-3 py-2">#{e.track_id}</td>
                      <td className="px-3 py-2"><span className="inline-flex items-center gap-2 capitalize"><span className="h-2 w-2 rounded-full" style={{ background: typeColor(e.vehicle_type) }} />{e.vehicle_type}</span></td>
                      <td className="px-3 py-2 capitalize">{e.direction}</td><td className="num px-3 py-2">{(e.confidence * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Async>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
          <label className="flex items-center gap-2 text-mute">Rows<select className="input !w-auto !py-1" value={size} onChange={(e) => { setSize(Number(e.target.value)); setPage(1) }}>{[10, 25, 50, 100].map((n) => <option key={n}>{n}</option>)}</select></label>
          <div className="flex items-center gap-2">
            <button className="btn px-2.5" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft size={15} /></button>
            <span className="num text-mute">Page {page} / {pages}</span>
            <button className="btn px-2.5" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight size={15} /></button>
          </div>
        </div>
      </Card>
    </>
  )
}
