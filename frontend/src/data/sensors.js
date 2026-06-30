const sensors = [
  {
    key: 'gas',
    name: '가스 센서',
    detail: 'MQ-2 가연성 가스',
    unit: 'ppm',
    base: 338,
    swing: 150,
    floor: 120,
    decimals: 0,
    caution: 600,
    warning: 900,
    danger: 1200,
  },
  {
    key: 'temp',
    name: '온도 센서',
    detail: '실시간 차체 온도',
    unit: '°C',
    base: 41.5,
    swing: 11,
    floor: 18,
    decimals: 1,
    caution: 50,
    warning: 70,
    danger: 90,
  },
  {
    key: 'water',
    name: '전면 수위 센서',
    detail: '전방 침수 감지',
    unit: '%',
    base: 23,
    swing: 26,
    floor: 0,
    decimals: 0,
    caution: 45,
    warning: 70,
    danger: 88,
  },
  {
    key: 'smoke',
    name: '연기 센서',
    detail: '광학식 연기 농도',
    unit: '%',
    base: 15,
    swing: 22,
    floor: 0,
    decimals: 0,
    caution: 38,
    warning: 62,
    danger: 82,
  },
]

const HISTORY = 36

const STATUS = {
  safe: { label: '정상', tone: '#15b886' },
  caution: { label: '주의', tone: '#f0820f' },
  warning: { label: '경고', tone: '#ee5d2b' },
  danger: { label: '위험', tone: '#e5484d' },
}

function round(value, decimals) {
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

function nextValue(sensor, previous) {
  const drift = (sensor.base - previous) * 0.12
  const jitter = (Math.random() - 0.5) * sensor.swing
  return round(Math.max(sensor.floor, previous + drift + jitter), sensor.decimals)
}

function seedHistory(sensor) {
  const out = []
  let value = sensor.base
  for (let i = 0; i < HISTORY; i += 1) {
    value = nextValue(sensor, value)
    out.push(value)
  }
  return out
}

function statusFor(sensor, value) {
  if (value >= sensor.danger) return 'danger'
  if (value >= sensor.warning) return 'warning'
  if (value >= sensor.caution) return 'caution'
  return 'safe'
}

export { sensors, HISTORY, STATUS, nextValue, seedHistory, statusFor }
