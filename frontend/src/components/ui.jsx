import { useEffect } from 'react'
import { AlertTriangle, Inbox, Loader2, X } from 'lucide-react'
import { LEVEL_COLORS } from '../utils/format'

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3 animate-rise">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-mute">{subtitle}</p>}
      </div>
      <div className="no-print flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

export function Card({ title, right, children, className = '' }) {
  return (
    <section className={`card p-4 animate-rise ${className}`}>
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-mute">{title}</h2>
          {right}
        </div>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, sub, color, icon: Icon }) {
  return (
    <div className="card relative overflow-hidden p-4 animate-rise">
      <div className="absolute inset-x-0 top-0 h-0.5" style={{ background: color || 'rgb(var(--amber))' }} />
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-mute">{label}</span>
        {Icon && <Icon size={16} style={{ color: color || 'rgb(var(--amber))' }} />}
      </div>
      <div className="num mt-2 text-3xl font-semibold">{value}</div>
      {sub && <div className="mt-1 text-xs text-mute">{sub}</div>}
    </div>
  )
}

export function Loading({ label = 'Loading…', height = 160 }) {
  return (
    <div className="flex items-center justify-center gap-2 text-sm text-mute" style={{ height }}>
      <Loader2 size={16} className="animate-spin" /> {label}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
      <AlertTriangle className="text-bad" size={22} />
      <p className="max-w-md text-sm text-bad">{message}</p>
      {onRetry && <button className="btn" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function EmptyState({ title = 'No data yet', hint, children }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <Inbox className="text-mute" size={26} />
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="max-w-sm text-xs text-mute">{hint}</p>}
      {children}
    </div>
  )
}

/** Wraps any useApi() result with consistent loading / error / empty handling. */
export function Async({ state, empty, emptyHint, height = 220, children }) {
  if (state.loading && !state.data) return <Loading height={height} />
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />
  const isEmpty = empty ? empty(state.data) : !state.data || (Array.isArray(state.data) && !state.data.length)
  if (isEmpty) return <div style={{ minHeight: height / 1.5 }}><EmptyState hint={emptyHint || 'Start a video on the Live Monitoring page to generate traffic data.'} /></div>
  return children(state.data)
}

const BADGES = {
  online: 'border-ok/40 text-ok bg-ok/10', processing: 'border-amber/50 text-amber bg-amber/10',
  offline: 'border-line text-mute', inactive: 'border-line text-mute', error: 'border-bad/50 text-bad bg-bad/10',
  starting: 'border-info/40 text-info bg-info/10', running: 'border-amber/50 text-amber bg-amber/10',
  finished: 'border-ok/40 text-ok bg-ok/10', stopped: 'border-line text-mute',
}
export function StatusBadge({ status }) {
  const live = status === 'processing' || status === 'running'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${BADGES[status] || BADGES.offline}`}>
      <span className={`h-1.5 w-1.5 rounded-full bg-current ${live ? 'animate-dot' : ''}`} />{status}
    </span>
  )
}

export function LevelBadge({ level }) {
  const c = LEVEL_COLORS[level] || LEVEL_COLORS.NO_DATA
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-semibold" style={{ borderColor: c + '88', color: c, background: c + '1a' }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: c }} />{level === 'NO_DATA' ? 'NO DATA' : level}
    </span>
  )
}

export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-[1500] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
        className={`card max-h-[92vh] w-full overflow-auto p-5 shadow-2xl animate-rise ${wide ? 'max-w-3xl' : 'max-w-lg'}`}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="text-mute hover:text-ink" aria-label="Close"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export const Field = ({ label, children, hint }) => (
  <label className="block">
    <span className="label">{label}</span>{children}
    {hint && <span className="mt-1 block text-xs text-mute">{hint}</span>}
  </label>
)
