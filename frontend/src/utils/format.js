export const TYPE_COLORS = { car: '#60a5fa', motorcycle: '#fbbf24', bus: '#f87171', truck: '#34d399' }
export const TYPES = ['car', 'motorcycle', 'bus', 'truck']
export const typeColor = (t) => TYPE_COLORS[t] || '#a78bfa'
export const LEVEL_COLORS = { LOW: '#34d399', MODERATE: '#fbbf24', HIGH: '#fb923c', CRITICAL: '#f85757', NO_DATA: '#64748b' }
export const nf = (n) => (n == null ? '–' : Number(n).toLocaleString())
export const pct = (n) => (n == null ? '–' : `${n > 0 ? '+' : ''}${n}%`)
export const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '')
export const fmtTime = (iso) => new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'medium' })
export const isoDate = (d) => d.toISOString().slice(0, 10)
export const daysAgo = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return isoDate(d) }
