import { useEffect } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { LEVEL_COLORS, nf } from '../utils/format'
import { LevelBadge, StatusBadge } from './ui'

function Fit({ points }) {
  const map = useMap()
  useEffect(() => {
    if (points.length === 1) map.setView(points[0], 13)
    else if (points.length > 1) map.fitBounds(points, { padding: [40, 40], maxZoom: 14 })
  }, [JSON.stringify(points)]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

/** Cameras on OpenStreetMap, coloured by current traffic level. No API key required. */
export default function TrafficMap({ cameras, height = 360 }) {
  const placed = cameras.filter((c) => c.latitude != null && c.longitude != null)
  const pts = placed.map((c) => [c.latitude, c.longitude])
  return (
    <div className="overflow-hidden rounded-lg border border-line" style={{ height }}>
      <MapContainer center={[20, 0]} zoom={2} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Fit points={pts} />
        {placed.map((c) => {
          const color = LEVEL_COLORS[c.traffic_level]
          return (
            <CircleMarker key={c.camera_id} center={[c.latitude, c.longitude]} radius={13}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.55, weight: 3 }}>
              <Popup>
                <div className="min-w-[200px] space-y-1.5 text-sm">
                  <div className="text-base font-semibold">{c.camera_name}</div>
                  <div className="text-xs opacity-70">{c.area_name || 'No area assigned'}</div>
                  <div className="flex items-center gap-2"><StatusBadge status={c.processing ? 'processing' : c.status} /><LevelBadge level={c.traffic_level} /></div>
                  <div>Vehicles today: <b className="num">{nf(c.vehicles_today)}</b></div>
                  <div className="text-xs opacity-70">Last 15 min: {nf(c.vehicles_last_15_min)} (≈ {nf(c.estimated_per_hour)}/h of {nf(c.hourly_capacity)}/h capacity)</div>
                </div>
              </Popup>
            </CircleMarker>
          )
        })}
      </MapContainer>
    </div>
  )
}
