import { useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import { TrafficProvider } from './components/TrafficProvider'
import AppLayout from './layouts/AppLayout'
import Dashboard from './pages/Dashboard'
import Live from './pages/Live'
import Cameras from './pages/Cameras'
import Areas from './pages/Areas'
import Analytics from './pages/Analytics'
import History from './pages/History'
import Reports from './pages/Reports'
import Settings from './pages/Settings'

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('tf-theme') || 'dark')
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('tf-theme', theme) }, [theme])
  return (
    <ToastProvider>
      <TrafficProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout theme={theme} setTheme={setTheme} />}>
              <Route index element={<Dashboard />} />
              <Route path="live" element={<Live />} />
              <Route path="cameras" element={<Cameras />} />
              <Route path="areas" element={<Areas />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="history" element={<History />} />
              <Route path="reports" element={<Reports />} />
              <Route path="settings" element={<Settings theme={theme} setTheme={setTheme} />} />
              <Route path="*" element={<p className="text-mute">Page not found.</p>} />
            </Route>
          </Routes>
        </BrowserRouter>
      </TrafficProvider>
    </ToastProvider>
  )
}
