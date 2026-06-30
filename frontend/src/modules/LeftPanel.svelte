<script>
  import ConnectionStatus from './ConnectionStatus.svelte'
  import WasdHint from './WasdHint.svelte'
  import SettingsButton from './SettingsButton.svelte'
  import SettingsModal from './SettingsModal.svelte'
  import Toast from './Toast.svelte'
  import { config } from '../config/config.js'

  const STORAGE_KEY = 'arduino-vmdi:server'

  function loadStoredServer() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return null
      const parsed = JSON.parse(raw)
      return {
        serverIp: typeof parsed.serverIp === 'string' ? parsed.serverIp : null,
        serverPort: Number.isFinite(parsed.serverPort) ? parsed.serverPort : null,
        apiPort: Number.isFinite(parsed.apiPort) ? parsed.apiPort : null,
      }
    } catch {
      return null
    }
  }

  function persistServer(next) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch {}
  }

  const stored = loadStoredServer()

  let systemName = $state(config.systemName)
  let serverIp = $state(stored?.serverIp ?? config.serverIp)
  let serverPort = $state(stored?.serverPort ?? config.serverPort)
  let apiPort = $state(stored?.apiPort ?? config.apiPort)
  let connected = $state(false)
  let checked = $state(false)
  let settingsOpen = $state(false)
  let toastOpen = $state(false)
  let videoEl = $state()
  let mediaStream = $state(null)

  let probeTimer = null
  let lastStats = null

  function stopLatencyProbe() {
    if (probeTimer) {
      clearInterval(probeTimer)
      probeTimer = null
    }
    lastStats = null
  }

  function startLatencyProbe(pc) {
    stopLatencyProbe()
    probeTimer = setInterval(async () => {
      try {
        const report = await pc.getStats()
        let inbound = null
        let candidatePair = null
        report.forEach((s) => {
          if (s.type === 'inbound-rtp' && s.kind === 'video') inbound = s
          if (s.type === 'candidate-pair' && s.state === 'succeeded' && s.nominated) candidatePair = s
        })
        if (!inbound) return
        let fps = inbound.framesPerSecond
        let jbDeltaMs = null
        let assemblyDeltaMs = null
        if (lastStats) {
          const dFrames = (inbound.jitterBufferEmittedCount ?? 0) - (lastStats.jitterBufferEmittedCount ?? 0)
          const dDelay = (inbound.jitterBufferDelay ?? 0) - (lastStats.jitterBufferDelay ?? 0)
          if (dFrames > 0) jbDeltaMs = (dDelay / dFrames) * 1000
          const dAFrames = (inbound.framesAssembledFromMultiplePackets ?? 0) - (lastStats.framesAssembledFromMultiplePackets ?? 0)
          const dADelay = (inbound.totalAssemblyTime ?? 0) - (lastStats.totalAssemblyTime ?? 0)
          if (dAFrames > 0) assemblyDeltaMs = (dADelay / dAFrames) * 1000
          if (fps == null) {
            const dDecoded = (inbound.framesDecoded ?? 0) - (lastStats.framesDecoded ?? 0)
            const dt = (inbound.timestamp - lastStats.timestamp) / 1000
            if (dt > 0) fps = dDecoded / dt
          }
        }
        lastStats = inbound
        console.log('[webrtc-stats]', {
          fps: fps != null ? Number(fps.toFixed(1)) : null,
          jitterBufferMs: jbDeltaMs != null ? Number(jbDeltaMs.toFixed(1)) : null,
          assemblyMs: assemblyDeltaMs != null ? Number(assemblyDeltaMs.toFixed(1)) : null,
          framesDropped: inbound.framesDropped,
          freezeCount: inbound.freezeCount,
          totalFreezesDurationMs: inbound.totalFreezesDuration != null ? Number((inbound.totalFreezesDuration * 1000).toFixed(0)) : null,
          rttMs: candidatePair?.currentRoundTripTime != null ? Number((candidatePair.currentRoundTripTime * 1000).toFixed(1)) : null,
        })
      } catch (err) {
        console.warn('getStats failed', err)
      }
    }, 1000)
  }

  function connect() {
    const host = serverIp.trim().replace(/^[a-z]+:\/\//i, '')
    connected = false
    if (!host) {
      checked = true
      return () => {}
    }

    const pc = new RTCPeerConnection({ iceServers: [] })
    const socket = new WebSocket(`ws://${host}:${serverPort}`)
    let closed = false

    const cleanup = () => {
      if (closed) return
      closed = true
      stopLatencyProbe()
      try { pc.close() } catch {}
      try { socket.close() } catch {}
      if (videoEl) videoEl.srcObject = null
      mediaStream = null
    }

    const sendSignal = (payload) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(payload))
      }
    }

    pc.ontrack = (event) => {
      const [stream] = event.streams
      mediaStream = stream
      connected = true
      checked = true
      try {
        const receiver = event.receiver ?? event.transceiver?.receiver
        if (receiver) {
          if ('playoutDelayHint' in receiver) receiver.playoutDelayHint = 0
          if ('jitterBufferTarget' in receiver) receiver.jitterBufferTarget = 0
        }
      } catch (err) {
        console.warn('low-latency hints not applied', err)
      }
      startLatencyProbe(pc)
    }

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal({
          type: 'candidate',
          candidate: event.candidate.candidate,
          sdpMid: event.candidate.sdpMid,
          sdpMLineIndex: event.candidate.sdpMLineIndex,
        })
      }
    }

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected' || pc.connectionState === 'closed') {
        connected = false
        checked = true
      }
    }

    const timeout = setTimeout(() => {
      if (!connected) cleanup()
    }, 5000)

    socket.onmessage = async (event) => {
      if (typeof event.data !== 'string') return
      let msg
      try { msg = JSON.parse(event.data) } catch { return }
      try {
        if (msg.type === 'offer') {
          await pc.setRemoteDescription({ type: 'offer', sdp: msg.sdp })
          const answer = await pc.createAnswer()
          await pc.setLocalDescription(answer)
          sendSignal({ type: 'answer', sdp: answer.sdp })
        } else if (msg.type === 'candidate') {
          await pc.addIceCandidate({
            candidate: msg.candidate,
            sdpMid: msg.sdpMid,
            sdpMLineIndex: msg.sdpMLineIndex,
          })
        }
      } catch (err) {
        console.error('signaling error', err)
      }
    }

    socket.onclose = () => {
      clearTimeout(timeout)
      cleanup()
      connected = false
      checked = true
    }

    socket.onerror = () => {
      clearTimeout(timeout)
    }

    return () => {
      clearTimeout(timeout)
      socket.onopen = socket.onclose = socket.onerror = socket.onmessage = null
      cleanup()
    }
  }

  $effect(() => {
    if (videoEl && mediaStream && videoEl.srcObject !== mediaStream) {
      videoEl.srcObject = mediaStream
    }
  })

  $effect(() => {
    let teardown = connect()
    const interval = setInterval(() => {
      if (!connected) {
        teardown()
        teardown = connect()
      }
    }, 5000)
    return () => {
      teardown()
      clearInterval(interval)
    }
  })
</script>

<section class="left">
  <div class="settings-corner">
    <SettingsButton onclick={() => (settingsOpen = true)} />
  </div>
  <div class="corner">
    <ConnectionStatus {connected} />
  </div>
  <main>
    {#if connected}
      <video class="stream" bind:this={videoEl} autoplay muted playsinline></video>
    {:else}
      <span class="eyebrow">{systemName}</span>
      <h1>{serverIp}</h1>
      <div class="connecting" role="status" aria-live="polite">
        <span class="connecting-label">연결 중</span>
        <span class="dots" aria-hidden="true">
          <span></span><span></span><span></span>
        </span>
      </div>
    {/if}
  </main>
  <WasdHint {serverIp} {apiPort} />
</section>

<SettingsModal
  open={settingsOpen}
  {serverIp}
  {serverPort}
  {apiPort}
  robotConnected={connected}
  onclose={() => (settingsOpen = false)}
  onsave={(next) => {
    serverIp = next.serverIp
    serverPort = next.serverPort
    apiPort = next.apiPort
    persistServer(next)
    settingsOpen = false
    toastOpen = true
  }}
/>

<Toast
  open={toastOpen}
  message="변경되었습니다!"
  onclose={() => (toastOpen = false)}
/>

<Toast
  open={checked && !connected}
  message="원격 제어 로봇과 연결이 끊겼습니다"
  tone="error"
  persistent
/>

<style>
  .left {
    position: relative;
    flex: 0 0 70%;
    display: flex;
    border-radius: 20px;
    border: 1px solid rgba(17, 24, 39, 0.04);
    background: #ffffff;
    box-shadow: 0 4px 16px rgba(17, 24, 39, 0.06);
  }

  .settings-corner {
    position: absolute;
    top: 16px;
    left: 16px;
  }

  .corner {
    position: absolute;
    top: 16px;
    right: 16px;
  }

  main {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1.6rem;
    width: 100%;
    height: 100%;
    padding: 58px 20px 60px;
  }

  .stream {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: 16px;
    background: #000;
  }

  .eyebrow {
    padding: 8px 18px;
    border-radius: 999px;
    background: rgba(49, 130, 246, 0.1);
    color: #3182f6;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  h1 {
    margin: 0;
    font-size: 80px;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.2;
    background: linear-gradient(135deg, #191f28 0%, #3a4856 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  .connecting {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    margin-top: 0.6rem;
    padding: 13px 24px;
    border-radius: 999px;
    background: #f2f4f6;
    color: #8b95a1;
    font-size: 17px;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .connecting-label {
    line-height: 1;
  }

  .dots {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .dots span {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: currentColor;
    animation: blink 1.4s infinite both;
  }

  .dots span:nth-child(2) {
    animation-delay: 0.2s;
  }

  .dots span:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes blink {
    0%,
    70%,
    100% {
      opacity: 0.25;
    }
    35% {
      opacity: 1;
    }
  }
</style>
