import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { useTrafficSocket } from '../hooks/useTrafficSocket'
import { useToast } from './Toast'

const Ctx = createContext(null)
export const useTraffic = () => useContext(Ctx)

/** Holds the live connection: recent events, per-camera processor state, and a `tick` that
 *  increments (debounced) whenever new data is stored so charts can refetch. */
export function TrafficProvider({ children }) {
  const toast = useToast()
  const [tick, setTick] = useState(0)
  const [events, setEvents] = useState([])
  const [states, setStates] = useState({})
  const timer = useRef(null)
  const lastStatus = useRef({})

  const bump = useCallback(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setTick((t) => t + 1), 700)
  }, [])

  const onMessage = useCallback((m) => {
    if (m.type === 'vehicle_event') {
      setEvents((e) => [m.event, ...e].slice(0, 40))
      bump()
    } else if (m.type === 'processor_state') {
      setStates((s) => ({ ...s, [m.camera_id]: m.state }))
      const prev = lastStatus.current[m.camera_id]
      const st = m.state.status
      if (prev !== st) {
        lastStatus.current[m.camera_id] = st
        if (st === 'error') toast.error(m.state.message || 'Processing failed')
        if (st === 'finished') { toast.info('Video finished processing'); bump() }
      }
    } else if (m.type === 'error') {
      toast.error(m.message)
    }
  }, [bump, toast])

  const socket = useTrafficSocket(onMessage)
  const value = useMemo(() => ({ tick, events, states, socket, bump }), [tick, events, states, socket, bump])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
