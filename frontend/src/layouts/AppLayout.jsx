import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Activity, BarChart3, Camera, Database, FileText, LayoutDashboard, MapPin, Menu, Moon, Radio, Settings, Sun } from 'lucide-react'
import { useTraffic } from '../components/TrafficProvider'
import { useApi } from '../hooks/useApi'

const NAV = [
  ['/', 'Dashboard', LayoutDashboard], ['/live', 'Live Monitoring', Radio], ['/cameras', 'Cameras', Camera],
  ['/areas', 'Areas', MapPin], ['/analytics', 'Traffic Analytics', BarChart3], ['/history', 'Historical Data', Database],
  ['/reports', 'Reports', FileText], ['/settings', 'Settings', Settings],
]

function Clock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t) }, [])
  return (
    <div className="num hidden text-right text-xs leading-tight text-mute sm:block">
      <div className="text-ink">{now.toLocaleTimeString()}</div>
      <div>{now.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}</div>
    </div>
  )
}

function SystemStatus() {
  const { socket } = useTraffic()
  const { data, error } = useApi('/health', null, { live: true })
  const dbOk = data?.database?.ok
  const parts = [
    ['API', !error && !!data], ['Database', !!dbOk], ['AI model', !!data?.model?.ok], ['Live', socket === 'open'],
  ]
  const allOk = parts.every(([, ok]) => ok)
  return (
    <div className="flex items-center gap-3 text-xs" title={parts.map(([n, ok]) => `${n}: ${ok ? 'ok' : 'attention'}`).join('\n')}>
      <span className={`flex items-center gap-1.5 font-medium ${allOk ? 'text-ok' : 'text-warn'}`}>
        <span className={`h-2 w-2 rounded-full bg-current ${allOk ? '' : 'animate-dot'}`} />
        {allOk ? 'All systems operational' : 'Attention needed'}
      </span>
      <span className="hidden gap-2 lg:flex">
        {parts.map(([n, ok]) => (
          <span key={n} className={`rounded border px-1.5 py-0.5 ${ok ? 'border-line text-mute' : 'border-bad/50 text-bad'}`}>{n}</span>
        ))}
      </span>
    </div>
  )
}

export default function AppLayout({ theme, setTheme }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex h-full">
      <aside className={`no-print fixed inset-y-0 left-0 z-40 w-60 border-r border-line bg-panel transition-transform lg:static lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-amber text-black"><Activity size={20} strokeWidth={2.5} /></div>
          <div className="leading-tight">
            <div className="text-[15px] font-semibold tracking-tight">TrafficFlow <span className="text-amber">AI</span></div>
            <div className="text-[10px] uppercase tracking-widest text-mute">Urban flow analytics</div>
          </div>
        </div>
        <nav className="mt-2 flex flex-col gap-0.5 px-3">
          {NAV.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${isActive ? 'bg-amber/10 font-medium text-amber' : 'text-mute hover:bg-panel2 hover:text-ink'}`}>
              <Icon size={17} /> {label}
            </NavLink>
          ))}
        </nav>
        <p className="absolute bottom-4 left-5 right-5 text-[11px] leading-snug text-mute">
          Privacy-first: only anonymous counts are stored. No plates, no faces, no video frames.
        </p>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={() => setOpen(false)} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print flex items-center justify-between gap-3 border-b border-line bg-panel/80 px-4 py-3 backdrop-blur lg:px-8">
          <div className="flex items-center gap-3">
            <button className="btn px-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={18} /></button>
            <SystemStatus />
          </div>
          <div className="flex items-center gap-4">
            <Clock />
            <button className="btn px-2.5" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-4 py-6 lg:px-8"><Outlet /></main>
      </div>
    </div>
  )
}
