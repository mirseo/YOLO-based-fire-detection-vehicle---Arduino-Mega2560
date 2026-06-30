<script>
  import { fly } from 'svelte/transition'

  let { serverIp = '', apiPort = 9001 } = $props()

  let visible = $state(true)
  let pressedKey = $state(null)
  let reappearTimer
  let socket = null

  $effect(() => {
    const host = serverIp.trim().replace(/^[a-z]+:\/\//i, '')
    const port = apiPort
    if (!host) return

    let active = true
    let sock = null
    let retryTimer

    const open = () => {
      if (!active) return
      try {
        sock = new WebSocket(`ws://${host}:${port}/ws/control`)
      } catch {
        retryTimer = setTimeout(open, 1000)
        return
      }
      socket = sock
      sock.onclose = () => {
        if (active) retryTimer = setTimeout(open, 1000)
      }
      sock.onerror = () => {
        try { sock.close() } catch {}
      }
    }

    open()

    return () => {
      active = false
      clearTimeout(retryTimer)
      socket = null
      if (sock) {
        try { sock.close() } catch {}
      }
    }
  })

  function sendControl(key) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(key)
    }
  }

  function isTyping(target) {
    if (!target) return false
    const tag = target.tagName
    return tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable
  }

  function handleKeydown(event) {
    if (isTyping(event.target)) return
    const key = event.key.toLowerCase()
    if (!['w', 'a', 's', 'd', 'x'].includes(key)) return
    if (event.repeat) return

    sendControl(key)

    clearTimeout(reappearTimer)
    reappearTimer = setTimeout(() => {
      visible = true
      pressedKey = null
    }, 6000)

    if (visible && !pressedKey) {
      pressedKey = key
      setTimeout(() => (visible = false), 180)
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if visible}
  <div class="wasd" transition:fly={{ y: 16, duration: 450 }}>
    <div class="row">
      <kbd class:pressed={pressedKey === 'w'}>W</kbd>
    </div>
    <div class="row">
      <kbd class:pressed={pressedKey === 'a'}>A</kbd>
      <kbd class:pressed={pressedKey === 's'}>S</kbd>
      <kbd class:pressed={pressedKey === 'd'}>D</kbd>
    </div>
  </div>
  <div class="stop" transition:fly={{ y: 16, duration: 450 }}>
    <kbd class:pressed={pressedKey === 'x'}>X</kbd>
  </div>
{/if}

<style>
  .wasd {
    position: absolute;
    bottom: 16px;
    left: 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .stop {
    position: absolute;
    bottom: 16px;
    right: 16px;
  }

  .row {
    display: flex;
    gap: 4px;
  }

  kbd {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 7px;
    border: 1px solid #e5e8eb;
    border-bottom-width: 2px;
    background: #ffffff;
    color: #4e5968;
    font-size: 12px;
    font-weight: 700;
    font-family: inherit;
    box-shadow: 0 1px 2px rgba(17, 24, 39, 0.06);
    transition: transform 0.08s ease, background 0.08s ease,
      border-color 0.08s ease, color 0.08s ease, box-shadow 0.08s ease;
  }

  kbd.pressed {
    transform: translateY(2px);
    border-color: #d1d6db;
    border-bottom-width: 1px;
    background: #e8ebed;
    color: #4e5968;
    box-shadow: none;
  }
</style>
