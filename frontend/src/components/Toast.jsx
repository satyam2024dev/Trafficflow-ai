import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

const Ctx = createContext(null)
export const useToast = () => useContext(Ctx)

const STYLE = {
  success: ['border-ok/40', 'text-ok', CheckCircle2],
  error: ['border-bad/50', 'text-bad', AlertTriangle],
  info: ['border-info/40', 'text-info', Info],
}

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const remove = useCallback((id) => setItems((i) => i.filter((t) => t.id !== id)), [])
  const push = useCallback((kind, message) => {
    const id = Math.random().toString(36).slice(2)
    setItems((i) => [...i.slice(-3), { id, kind, message }])
    setTimeout(() => remove(id), kind === 'error' ? 8000 : 4000)
  }, [remove])
  const api = useMemo(() => ({
    success: (m) => push('success', m), error: (m) => push('error', m), info: (m) => push('info', m),
  }), [push])

  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="no-print fixed bottom-4 right-4 z-[2000] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite">
        {items.map((t) => {
          const [border, color, Icon] = STYLE[t.kind]
          return (
            <div key={t.id} className={`card animate-slideIn flex items-start gap-3 p-3 shadow-xl ${border}`}>
              <Icon size={18} className={`mt-0.5 shrink-0 ${color}`} />
              <p className="flex-1 text-sm">{t.message}</p>
              <button onClick={() => remove(t.id)} className="text-mute hover:text-ink" aria-label="Dismiss"><X size={16} /></button>
            </div>
          )
        })}
      </div>
    </Ctx.Provider>
  )
}
