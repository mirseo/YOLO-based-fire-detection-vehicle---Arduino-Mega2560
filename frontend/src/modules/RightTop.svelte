<script>
  import { onMount, onDestroy } from 'svelte'
  import { sensors, minutes, MIN, MAX, TEMP_FIELDS } from '../data/temperature.js'
  import { heatmap } from '../state/heatmap.svelte.js'
  import SensorGrid from './SensorGrid.svelte'
  import { config } from '../config/config.js'

  const STORAGE_KEY = 'arduino-vmdi:server'

  function loadServerConfig() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return { serverIp: config.serverIp, apiPort: config.apiPort }
      const p = JSON.parse(raw)
      return {
        serverIp: typeof p.serverIp === 'string' ? p.serverIp : config.serverIp,
        apiPort: Number.isFinite(p.apiPort) ? p.apiPort : config.apiPort,
      }
    } catch {
      return { serverIp: config.serverIp, apiPort: config.apiPort }
    }
  }

  let selected = $state('temp')
  let hovered = $state(null)
  let scaleHover = $state(null)
  let initialized = false
  let now = $state(new Date())
  let clockTimer = null

  let cellColors = $derived(heatmap.readings.map((row) => row.map((temp) => colorFor(temp))))

  let timer = null

  function colorFor(temp) {
    const norm = Math.min(1, Math.max(0, (temp - MIN) / (MAX - MIN)))
    const hue = 210 - norm * 210
    return `hsl(${hue}, 68%, 56%)`
  }

  function pad(value) {
    return String(value).padStart(2, '0')
  }

  function minuteToTime(m) {
    const d = new Date(now.getTime() - (58 - m) * 60 * 1000)
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  function safetyFor(temp) {
    if (temp < 40) return { label: '안전 · 대원 진입 및 활동 가능', tone: 'safe' }
    if (temp < 60) return { label: '주의 · 보호장비 착용 후 진입', tone: 'caution' }
    if (temp < 90) return { label: '경고 · 화상 위험, 접근 시간 최소화', tone: 'warning' }
    return { label: '위험 · 대원 진입 금지, 즉시 대피', tone: 'danger' }
  }

  function onScaleMove(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
    scaleHover = { ratio, temp: MIN + ratio * (MAX - MIN) }
  }

  async function fetchReadings() {
    const { serverIp, apiPort } = loadServerConfig()
    try {
      const res = await fetch(`http://${serverIp}:${apiPort}/api/sensors`)
      if (!res.ok) {
        console.log('[temp heatmap] /api/sensors HTTP error', res.status)
        return
      }
      const data = await res.json()
      console.log('[temp heatmap] /api/sensors response', data)
      const vals = TEMP_FIELDS.map((f) => data[f] ?? 0)
      if (!initialized) {
        heatmap.set(vals.map((v) => minutes.map(() => v)))
        initialized = true
      } else {
        heatmap.set(heatmap.readings.map((row, si) => [...row.slice(1), vals[si]]))
      }
    } catch (err) {
      console.log('[temp heatmap] fetch error', err)
    }
  }

  onMount(() => {
    fetchReadings()
    timer = setInterval(fetchReadings, 2 * 60 * 1000)
    clockTimer = setInterval(() => { now = new Date() }, 60000)
  })

  onDestroy(() => {
    clearInterval(timer)
    clearInterval(clockTimer)
  })
</script>

<section class="right-top">
  <header class="header">
    {#if selected === 'temp'}
      <div class="caption">
        {#if hovered}
          <strong>{sensors[hovered.si].name}</strong>
          <span>{minuteToTime(hovered.m)}</span>
          <span class="value" style:color={colorFor(heatmap.readings[hovered.si][hovered.mi])}>
            {heatmap.readings[hovered.si][hovered.mi].toFixed(1)}°C
          </span>
        {:else}
          <strong>분별 온도 히트맵</strong>
          <span>센서 5곳 · 1시간</span>
        {/if}
      </div>
    {:else}
      <div class="caption">
        <strong>실시간 센서</strong>
      </div>
    {/if}
    <div class="toggle">
      <button class="option" class:active={selected === 'temp'} onclick={() => (selected = 'temp')}>
        온도
      </button>
      <button
        class="option"
        class:active={selected === 'sensor'}
        onclick={() => (selected = 'sensor')}
      >
        센서
      </button>
    </div>
  </header>

  {#if selected === 'temp'}
    <div class="heatmap">
      <div class="grid">
        {#each sensors as sensor, si}
          <span class="row-label">{sensor.name}</span>
          {#each minutes as m, mi}
            <div
              class="cell"
              style:background={cellColors[si][mi]}
              role="img"
              aria-label={`${sensor.name} ${minuteToTime(m)} — ${heatmap.readings[si][mi].toFixed(1)}°C`}
              title={`${sensor.name} ${minuteToTime(m)} — ${heatmap.readings[si][mi].toFixed(1)}°C`}
              onmouseenter={() => (hovered = { si, mi, m })}
              onmouseleave={() => (hovered = null)}
            ></div>
          {/each}
        {/each}
      </div>

      <div class="minute-axis">
        <span></span>
        {#each minutes as m}
          <span class="tick">{m % 10 === 0 ? minuteToTime(m) : ''}</span>
        {/each}
      </div>

      <div class="legend">
        <span>{MIN}°C</span>
        <div class="scale-wrap">
          <div
            class="scale"
            role="presentation"
            onmousemove={onScaleMove}
            onmouseleave={() => (scaleHover = null)}
          ></div>
          {#if scaleHover}
            {@const safety = safetyFor(scaleHover.temp)}
            <div class="scale-marker" style:left={`${scaleHover.ratio * 100}%`}></div>
            <div class="scale-tip {safety.tone}" style:left={`${scaleHover.ratio * 100}%`}>
              <strong>{scaleHover.temp.toFixed(1)}°C</strong>
              <span>{safety.label}</span>
            </div>
          {/if}
        </div>
        <span>{MAX}°C</span>
      </div>
    </div>
  {:else}
    <SensorGrid />
  {/if}
</section>

<style>
  .right-top {
    flex: 0 0 30%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    border-radius: 20px;
    border: 1px solid rgba(17, 24, 39, 0.04);
    background: linear-gradient(162deg, #eef5ff 0%, #ffffff 72%);
    box-shadow: 0 4px 16px rgba(17, 24, 39, 0.06);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .caption {
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;
    font-size: 13px;
    color: #8b95a1;
    font-weight: 600;
  }

  .caption strong {
    font-size: 15px;
    font-weight: 700;
    color: #191f28;
  }

  .caption .value {
    font-weight: 700;
  }

  .toggle {
    display: inline-flex;
    gap: 2px;
    padding: 3px;
    border-radius: 999px;
    background: #f2f4f6;
    flex-shrink: 0;
    margin-left: auto;
  }

  .option {
    padding: 7px 16px;
    border: none;
    border-radius: 999px;
    background: transparent;
    font-family: inherit;
    font-size: 13px;
    font-weight: 700;
    color: #8b95a1;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }

  .option.active {
    background: #ffffff;
    color: #3182f6;
    box-shadow: 0 1px 3px rgba(17, 24, 39, 0.1);
  }

  .heatmap {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
    --label-w: 44px;
  }

  .grid {
    flex: 1;
    display: grid;
    grid-template-columns: var(--label-w) repeat(30, 1fr);
    grid-auto-rows: 1fr;
    gap: 3px;
    min-height: 0;
  }

  .row-label {
    display: flex;
    align-items: center;
    font-size: 12px;
    font-weight: 700;
    color: #4e5968;
  }

  .cell {
    border-radius: 3px;
    cursor: pointer;
    transition: opacity 0.12s ease, transform 0.12s ease,
      box-shadow 0.12s ease;
  }

  .cell:hover {
    transform: scale(1.18);
    box-shadow: 0 2px 8px rgba(17, 24, 39, 0.25);
  }

  .grid:has(.cell:hover) .cell:not(:hover) {
    opacity: 0.35;
  }

  .minute-axis {
    display: grid;
    grid-template-columns: var(--label-w) repeat(30, 1fr);
  }

  .tick {
    font-size: 9px;
    font-weight: 600;
    color: #b0b8c1;
    text-align: center;
  }

  .legend {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
    font-weight: 700;
    color: #8b95a1;
  }

  .scale-wrap {
    position: relative;
    flex: 1;
    display: flex;
  }

  .scale {
    flex: 1;
    height: 6px;
    border-radius: 999px;
    cursor: crosshair;
    background: linear-gradient(
      to right,
      hsl(210, 68%, 56%),
      hsl(105, 68%, 56%),
      hsl(0, 68%, 56%)
    );
  }

  .scale-marker {
    position: absolute;
    top: -2px;
    width: 2px;
    height: 10px;
    border-radius: 1px;
    background: #191f28;
    transform: translateX(-50%);
    pointer-events: none;
  }

  .scale-tip {
    position: absolute;
    bottom: 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    padding: 5px 9px;
    border-radius: 8px;
    white-space: nowrap;
    color: #ffffff;
    box-shadow: 0 4px 12px rgba(17, 24, 39, 0.2);
    transform: translateX(-50%);
    pointer-events: none;
  }

  .scale-tip strong {
    font-size: 12px;
  }

  .scale-tip.safe {
    background: #15b886;
  }

  .scale-tip.caution {
    background: #f0820f;
  }

  .scale-tip.warning {
    background: #ee5d2b;
  }

  .scale-tip.danger {
    background: #e5484d;
  }
</style>
