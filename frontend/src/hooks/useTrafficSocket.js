import { useEffect, useRef, useState } from 'react'

/** WebSocket with automatic reconnect (exponential backoff) and keep-alive pings. */
export function useTrafficSocket(onMessage) {
  const [status, setStatus] = useState('connecting') // connecting | open | closed
  const handler = useRef(onMessage)
  handler.current = onMessage

  useEffect(() => {
    let ws, timer, ping, retry = 0, stopped = false
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/traffic`)
      setStatus('connecting')
      ws.onopen = () => {
        retry = 0; setStatus('open')
        ping = setInterval(() => ws.readyState === 1 && ws.send('ping'), 20000)
      }
      ws.onmessage = (e) => { try { handler.current(JSON.parse(e.data)) } catch { /* ignore malformed */ } }
      ws.onclose = () => {
        clearInterval(ping); setStatus('closed')
        if (!stopped) { timer = setTimeout(connect, Math.min(1000 * 2 ** retry++, 15000)) }
      }
      ws.onerror = () => ws.close()
    }
    connect()
    return () => { stopped = true; clearTimeout(timer); clearInterval(ping); ws && ws.close() }
  }, [])
  return status
}
