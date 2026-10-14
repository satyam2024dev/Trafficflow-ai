import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import { useTraffic } from '../components/TrafficProvider'

/** GET a resource with loading/error state. `live: true` refetches when the WebSocket reports new events. */
export function useApi(path, params, { live = false, enabled = true } = {}) {
  const { tick } = useTraffic()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const key = JSON.stringify([path, params])
  const seq = useRef(0)

  const load = useCallback(async () => {
    if (!enabled) return
    const mine = ++seq.current
    try {
      const d = await api.get(path, params)
      if (mine === seq.current) { setData(d); setError(null) }
    } catch (e) {
      if (mine === seq.current) setError(e.message)
    } finally {
      if (mine === seq.current) setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled])

  useEffect(() => { setLoading(true); load() }, [load])
  useEffect(() => { if (live && tick > 0) load() }, [tick]) // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, loading, reload: load }
}
