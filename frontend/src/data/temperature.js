const sensors = [
  { name: '전면' },
  { name: '좌측' },
  { name: '우측' },
  { name: '후면' },
  { name: '상단' },
]

const STEP = 2
const minutes = Array.from({ length: 60 / STEP }, (_, i) => i * STEP)
const MIN = 0
const MAX = 100

const TEMP_FIELDS = ['front_temp', 'left_temp', 'right_temp', 'rear_temp', 'top_temp']

function buildTemperatureCsv(readings) {
  function pad(v) {
    return String(v).padStart(2, '0')
  }
  const header = ['센서', ...minutes.map((m) => `${pad(m)}분`)]
  const rows = sensors.map((sensor, si) => [
    sensor.name,
    ...readings[si].map((v) => v.toFixed(1)),
  ])
  return [header, ...rows].map((row) => row.join(',')).join('\r\n')
}

function buildExportCsv(rows) {
  const grouped = new Map()
  for (const { ts, sensor_id, value } of rows) {
    if (!grouped.has(ts)) grouped.set(ts, new Array(5).fill(''))
    grouped.get(ts)[sensor_id] = value.toFixed(1)
  }
  const sorted = [...grouped.entries()].sort(([a], [b]) => a - b)
  const header = ['timestamp', 'front_temp', 'left_temp', 'right_temp', 'rear_temp', 'top_temp']
  const dataRows = sorted.map(([ts, vals]) => {
    const d = new Date(ts * 1000)
    const pad = (n) => String(n).padStart(2, '0')
    const dateStr = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    return [dateStr, ...vals]
  })
  return [header, ...dataRows].map((row) => row.join(',')).join('\r\n')
}

export { sensors, minutes, MIN, MAX, TEMP_FIELDS, buildTemperatureCsv, buildExportCsv }
