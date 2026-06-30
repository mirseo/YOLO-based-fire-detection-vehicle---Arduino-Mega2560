<script>
  import { fade, scale } from 'svelte/transition'
  import { buildExportCsv } from '../data/temperature.js'
  import { saveCsv } from '../data/download.js'

  const ipv4Pattern =
    /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/
  const domainPattern =
    /^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$/

  let {
    open = false,
    serverIp = '',
    serverPort = 9000,
    apiPort = 9001,
    robotConnected = false,
    onclose,
    onsave,
  } = $props()

  let ipValue = $state('')
  let ipError = $state('')
  let ipInput = $state()
  let portsValue = $state('')
  let portsError = $state('')
  let portsInput = $state()
  let connectionStatus = $state('checking')
  const robotStatus = $derived(robotConnected ? 'connected' : 'disconnected')

  const connectionLabel = $derived(
    connectionStatus === 'connected'
      ? '연결됨'
      : connectionStatus === 'disconnected'
        ? '연결 안 됨'
        : '확인 중...'
  )

  const robotLabel = $derived(robotConnected ? '연결됨' : '연결 안 됨')

  $effect(() => {
    if (open) {
      ipValue = serverIp
      ipError = ''
      portsValue = `${serverPort}, ${apiPort}`
      portsError = ''
      checkConnection()
    }
  })

  async function checkConnection() {
    connectionStatus = 'checking'
    try {
      await fetch('https://ipc.artsnoa.com', { method: 'GET', mode: 'no-cors' })
      connectionStatus = 'connected'
    } catch {
      connectionStatus = 'disconnected'
    }
  }

  function validateAddress(value) {
    if (value === 'localhost') {
      return { type: 'host', error: '' }
    }
    if (/^[\d.]+$/.test(value)) {
      return ipv4Pattern.test(value)
        ? { type: 'ip', error: '' }
        : { type: 'ip', error: '유효한 IP 주소를 입력해주세요' }
    }
    return domainPattern.test(value)
      ? { type: 'domain', error: '' }
      : { type: 'domain', error: '유효한 도메인 주소를 입력해주세요' }
  }

  function validatePort(value) {
    if (!/^\d+$/.test(value)) {
      return '포트 번호는 숫자만 입력할 수 있어요'
    }
    const port = Number(value)
    if (port < 1 || port > 65535) {
      return '포트 번호는 1에서 65535 사이여야 해요'
    }
    return ''
  }

  function save() {
    const address = ipValue.trim()
    const { error } = validateAddress(address)
    if (error) {
      ipError = error
      ipInput?.focus()
      return
    }
    const parts = portsValue.split(',').map((s) => s.trim())
    if (parts.length !== 2) {
      portsError = '포트를 쉼표로 구분하여 두 개 입력해주세요'
      portsInput?.focus()
      return
    }
    const [p1, p2] = parts
    const p1Err = validatePort(p1)
    if (p1Err) {
      portsError = p1Err
      portsInput?.focus()
      return
    }
    const p2Err = validatePort(p2)
    if (p2Err) {
      portsError = p2Err
      portsInput?.focus()
      return
    }
    onsave?.({
      serverIp: address,
      serverPort: Number(p1),
      apiPort: Number(p2),
    })
  }

  function handleKeydown(event) {
    if (open && event.key === 'Escape') onclose?.()
  }

  function handleOverlayClick(event) {
    if (event.target === event.currentTarget) onclose?.()
  }

  async function downloadTemperature() {
    const res = await fetch(`http://${serverIp}:${apiPort}/api/temp/export`)
    const { rows } = await res.json()
    saveCsv('temperature-export.csv', buildExportCsv(rows))
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <div
    class="overlay"
    role="presentation"
    onclick={handleOverlayClick}
    transition:fade={{ duration: 150 }}
  >
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
      transition:scale={{ start: 0.96, duration: 200 }}
    >
      <header>
        <div class="head-text">
          <h2 id="settings-title">설정</h2>
          <p>연결 환경과 표시 정보를 설정해 주세요</p>
        </div>
        <button class="close" onclick={onclose} aria-label="닫기">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M6 6L18 18M18 6L6 18"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
        </button>
      </header>

      <div class="fields">
        <div class="field">
          <label for="server-ip">제어 IP</label>
          <input
            id="server-ip"
            type="text"
            placeholder="192.168.0.1, localhost 또는 robot.example.com"
            class:invalid={ipError}
            bind:this={ipInput}
            bind:value={ipValue}
            oninput={() => (ipError = '')}
            onkeydown={(e) => e.key === 'Enter' && save()}
          />
          {#if ipError}
            <span class="error">{ipError}</span>
          {:else}
            <span class="hint">원격 제어 로봇의 IP 주소, localhost 또는 도메인 주소를 입력해주세요</span>
          {/if}
        </div>

        <div class="field">
          <label for="server-ports">포트 번호</label>
          <input
            id="server-ports"
            type="text"
            placeholder="9000, 9001"
            class:invalid={portsError}
            bind:this={portsInput}
            bind:value={portsValue}
            oninput={() => (portsError = '')}
            onkeydown={(e) => e.key === 'Enter' && save()}
          />
          {#if portsError}
            <span class="error">{portsError}</span>
          {:else}
            <span class="hint">WebSocket 포트, API 서버 포트 순서로 쉼표로 구분하여 입력해주세요</span>
          {/if}
        </div>
      </div>

      <div class="connection">
        <span>인터넷 연결 여부</span>
        <span class="status status-{connectionStatus}">
          <span class="dot"></span>
          {connectionLabel}
        </span>
      </div>

      <div class="connection">
        <span>원격 제어 로봇 연결 여부</span>
        <span class="status status-{robotStatus}">
          <span class="dot"></span>
          {robotLabel}
        </span>
      </div>

      <div class="data-export">
        <div class="data-text">
          <span class="data-title">온도 데이터</span>
          <span class="data-desc">측정된 온도 기록을 CSV로 저장하기</span>
        </div>
        <button class="export-btn" type="button" onclick={downloadTemperature}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          CSV 다운로드
        </button>
      </div>

      <footer>
        <button class="secondary" onclick={onclose}>취소</button>
        <button class="primary" onclick={save}>저장</button>
      </footer>
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: rgba(17, 24, 39, 0.45);
    backdrop-filter: blur(2px);
  }

  .modal {
    width: 100%;
    max-width: 560px;
    display: flex;
    flex-direction: column;
    padding: 40px;
    background: #ffffff;
    border-radius: 28px;
    box-shadow: 0 20px 60px rgba(17, 24, 39, 0.24);
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 32px;
  }

  .head-text {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #191f28;
  }

  .head-text p {
    margin: 0;
    font-size: 14px;
    line-height: 1.5;
    color: #8b95a1;
  }

  .close {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    margin: -4px -4px 0 0;
    border: none;
    border-radius: 10px;
    background: none;
    color: #8b95a1;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }

  .close:hover {
    background: #f2f4f6;
    color: #4e5968;
  }

  .fields {
    display: flex;
    flex-direction: column;
    gap: 24px;
    margin-bottom: 36px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  label {
    font-size: 13px;
    font-weight: 600;
    color: #4e5968;
  }

  input {
    width: 100%;
    height: 54px;
    padding: 0 18px;
    border: 1px solid #e5e8eb;
    border-radius: 14px;
    background: #ffffff;
    font-size: 15px;
    font-family: inherit;
    color: #191f28;
    outline: none;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  input::placeholder {
    color: #c1c8d0;
  }

  input:focus {
    border-color: #3182f6;
    box-shadow: 0 0 0 4px rgba(49, 130, 246, 0.12);
  }

  input.invalid {
    border-color: #f04452;
  }

  input.invalid:focus {
    box-shadow: 0 0 0 4px rgba(240, 68, 82, 0.12);
  }

  .hint {
    font-size: 13px;
    line-height: 1.5;
    color: #8b95a1;
  }

  .error {
    font-size: 13px;
    line-height: 1.5;
    color: #f04452;
  }

  .connection {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    font-size: 13px;
    font-weight: 600;
    color: #4e5968;
  }

  .data-export {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin: 4px 0 24px;
    padding: 16px 18px;
    border-radius: 14px;
    background: #f9fafb;
  }

  .data-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .data-title {
    font-size: 14px;
    font-weight: 600;
    color: #191f28;
  }

  .data-desc {
    font-size: 12px;
    line-height: 1.5;
    color: #8b95a1;
  }

  .export-btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    height: 40px;
    padding: 0 16px;
    border: 1px solid #e5e8eb;
    border-radius: 10px;
    background: #ffffff;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    color: #4e5968;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease;
  }

  .export-btn:hover {
    background: #f2f4f6;
    border-color: #d1d6db;
  }

  .status {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .status-checking {
    color: #8b95a1;
  }

  .status-checking .dot {
    background: #c1c8d0;
  }

  .status-connected {
    color: #15b06e;
  }

  .status-connected .dot {
    background: #15b06e;
  }

  .status-disconnected {
    color: #f04452;
  }

  .status-disconnected .dot {
    background: #f04452;
  }

  footer {
    display: flex;
    gap: 10px;
  }

  footer button {
    flex: 1;
    height: 54px;
    border: none;
    border-radius: 14px;
    font-size: 16px;
    font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .secondary {
    background: #f2f4f6;
    color: #4e5968;
  }

  .secondary:hover {
    background: #e8ebed;
  }

  .primary {
    background: #3182f6;
    color: #ffffff;
  }

  .primary:hover {
    background: #1b64da;
  }
</style>
