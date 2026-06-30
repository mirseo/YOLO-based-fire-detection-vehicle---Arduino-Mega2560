<script>
  import { onMount, onDestroy } from 'svelte'
  import { sensors, STATUS, statusFor } from '../data/sensors.js'
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

  let values = $state([0, 0, 0, 0])
  let hovered = $state(null)
  let timer = null

  const advice = {
    gas: {
      safe: '대원 활동 가능',
      caution: '환기 및 점화원 차단',
      warning: '방독면 착용 후 진입',
      danger: '폭발 가능, 즉시 대피',
    },
    temp: {
      safe: '대원 활동 가능',
      caution: '보호장비 점검 필요',
      warning: '화상 주의, 접근 최소화',
      danger: '진입 금지, 즉시 대피',
    },
    water: {
      safe: '침수 위협 없음',
      caution: '전방 침수 진행',
      warning: '장비 침수 임박',
      danger: '대원 대피 · 차량 이동',
    },
    smoke: {
      safe: '시야 확보 양호',
      caution: '마스크 착용 권장',
      warning: '호흡 곤란 우려',
      danger: 'SCBA 필수, 즉시 대피',
    },
  }

  function toWaterPercent(raw) {
    return Math.min(100, Math.max(0, Math.round((raw / 1023) * 100 / 61 * 100)))
  }

  async function fetchSensors() {
    const { serverIp, apiPort } = loadServerConfig()
    try {
      let data
      if (window.sensorAPI) {
        data = await window.sensorAPI.getSensors(serverIp, apiPort)
      } else {
        const res = await fetch(`http://${serverIp}:${apiPort}/api/sensors`)
        data = await res.json()
      }
      if (!data) return
      values = [
        data.gas ?? values[0],
        data.front_temp ?? values[1],
        data.water != null ? toWaterPercent(data.water) : values[2],
        values[3],
      ]
    } catch (err) {
      console.error('[sensor] error', err)
    }
  }

  onMount(() => {
    fetchSensors()
    timer = setInterval(fetchSensors, 1000)
  })

  onDestroy(() => clearInterval(timer))
</script>

<div class="table">
  {#each sensors as sensor, index}
    {@const tone = statusFor(sensor, values[index])}
    {@const status = STATUS[tone]}
    <div
      class="cell"
      class:hovered={hovered === index}
      style:--tone={status.tone}
      onmouseenter={() => (hovered = index)}
      onmouseleave={() => (hovered = null)}
      role="img"
      aria-label={`${sensor.name} ${values[index].toFixed(sensor.decimals)}${sensor.unit} — ${status.label} · ${advice[sensor.key][tone]}`}
    >
      {#if hovered === index}
        <span class="status-label">{status.label}</span>
        <span class="status-text">{advice[sensor.key][tone]}</span>
      {:else}
        <span class="name">{sensor.name}</span>
        <span class="value">{values[index].toFixed(sensor.decimals)} {sensor.unit}</span>
      {/if}
    </div>
  {/each}
</div>

<style>
  .table {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
  }

  .cell {
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 4px;
    min-width: 0;
    padding: 8px 6px;
    border-radius: 10px;
    background: #ffffff;
    border: 1px solid rgba(17, 24, 39, 0.06);
    text-align: center;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease,
      box-shadow 0.15s ease, transform 0.15s ease;
  }

  .cell.hovered {
    background: var(--tone);
    border-color: var(--tone);
    transform: translateY(-1px);
    box-shadow: 0 6px 14px color-mix(in srgb, var(--tone) 32%, transparent);
  }

  .name {
    font-size: 11px;
    font-weight: 600;
    color: #4e5968;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .value {
    font-size: 14px;
    font-weight: 700;
    color: #191f28;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .status-label {
    font-size: 10px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.02em;
    opacity: 0.85;
  }

  .status-text {
    font-size: 12px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.25;
    white-space: normal;
    word-break: keep-all;
  }
</style>
