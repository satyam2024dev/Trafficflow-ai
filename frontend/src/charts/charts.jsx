import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TYPES, typeColor } from '../utils/format'

const axis = { stroke: 'rgb(var(--mute))', fontSize: 11, tickLine: false, axisLine: { stroke: 'rgb(var(--line))' } }
const tip = {
  contentStyle: { background: 'rgb(var(--panel))', border: '1px solid rgb(var(--line))', borderRadius: 8, fontSize: 12, color: 'rgb(var(--ink))' },
  labelStyle: { color: 'rgb(var(--mute))' }, cursor: { fill: 'rgb(var(--amber) / 0.08)' },
}
const grid = <CartesianGrid stroke="rgb(var(--line))" strokeDasharray="3 3" vertical={false} />
const Box = ({ h = 260, children }) => <div style={{ height: h }}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>

export function HourlyChart({ data }) {
  return (
    <Box><AreaChart data={data} margin={{ left: -18, right: 8, top: 8 }}>
      <defs><linearGradient id="gh" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="rgb(255,176,32)" stopOpacity={0.45} /><stop offset="100%" stopColor="rgb(255,176,32)" stopOpacity={0} /></linearGradient></defs>
      {grid}<XAxis dataKey="label" {...axis} interval="preserveStartEnd" minTickGap={24} /><YAxis allowDecimals={false} {...axis} />
      <Tooltip {...tip} /><Area type="monotone" dataKey="count" name="Vehicles" stroke="rgb(255,176,32)" strokeWidth={2} fill="url(#gh)" />
    </AreaChart></Box>
  )
}

export function TypeBar({ data }) {
  return (
    <Box><BarChart data={data} margin={{ left: -18, right: 8, top: 8 }}>
      {grid}<XAxis dataKey="vehicle_type" {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} />
      <Bar dataKey="count" name="Vehicles" radius={[6, 6, 0, 0]}>{data.map((d) => <Cell key={d.vehicle_type} fill={typeColor(d.vehicle_type)} />)}</Bar>
    </BarChart></Box>
  )
}

export function AreaCompare({ data }) {
  return (
    <Box><BarChart data={data} margin={{ left: -18, right: 8, top: 8 }}>
      {grid}<XAxis dataKey="area_name" {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
      {TYPES.map((t) => <Bar key={t} dataKey={t} stackId="a" fill={typeColor(t)} />)}
    </BarChart></Box>
  )
}

export function TrendLine({ data, keyName = 'count' }) {
  return (
    <Box><LineChart data={data} margin={{ left: -18, right: 8, top: 8 }}>
      {grid}<XAxis dataKey="label" {...axis} interval="preserveStartEnd" minTickGap={20} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} />
      <Line type="monotone" dataKey={keyName} name="Vehicles" stroke="rgb(96,165,250)" strokeWidth={2.5} dot={{ r: 2.5 }} activeDot={{ r: 5 }} />
    </LineChart></Box>
  )
}

const DIR = ['#ffb020', '#60a5fa', '#34d399', '#f87171', '#a78bfa']
export function DirectionPie({ data }) {
  return (
    <Box><PieChart>
      <Pie data={data} dataKey="count" nameKey="direction" innerRadius={55} outerRadius={90} paddingAngle={3} stroke="none">
        {data.map((d, i) => <Cell key={d.direction} fill={DIR[i % DIR.length]} />)}
      </Pie>
      <Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
    </PieChart></Box>
  )
}

export function PeakChart({ data }) {
  const max = Math.max(...data.map((d) => d.avg_per_day), 0)
  return (
    <Box><BarChart data={data} margin={{ left: -18, right: 8, top: 8 }}>
      {grid}<XAxis dataKey="hour" {...axis} tickFormatter={(h) => `${h}h`} interval={1} /><YAxis {...axis} /><Tooltip {...tip} labelFormatter={(h) => `${String(h).padStart(2, '0')}:00`} />
      <Bar dataKey="avg_per_day" name="Avg vehicles/day" radius={[4, 4, 0, 0]}>
        {data.map((d) => <Cell key={d.hour} fill={d.avg_per_day === max && max > 0 ? '#f85757' : '#ffb020'} fillOpacity={d.avg_per_day === max && max > 0 ? 1 : 0.65} />)}
      </Bar>
    </BarChart></Box>
  )
}
