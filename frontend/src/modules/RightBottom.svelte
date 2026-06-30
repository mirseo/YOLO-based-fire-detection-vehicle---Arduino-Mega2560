<script>
  import { onMount, onDestroy } from 'svelte'
  import { config } from '../config/config.js'

  const STORAGE_KEY = 'arduino-vmdi:server'
  const LIVE_INTERVAL_MS = 10000

  let question = $state('')
  let mode = $state('live')
  let display = $state('')
  let userQuestion = $state('')
  let streaming = $state(false)
  let updatedAt = $state('')
  let spinning = $state(false)
  let lastQuestion = $state('')
  let chatBody = $state(null)

  function renderMarkdown(text) {
    return text
      .replace(/^#{1,6} ?/gm, '')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  }

  let runId = 0
  let liveTimer = null
  let revertTimer = null

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

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  function nowLabel() {
    const date = new Date()
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  }

  let scrollPending = false
  function requestScroll() {
    if (scrollPending) return
    scrollPending = true
    requestAnimationFrame(() => {
      scrollPending = false
      if (chatBody) chatBody.scrollTop = chatBody.scrollHeight
    })
  }

  function delayFor(char) {
    if (char === ' ' || char === '\n') return 16
    if ('.,!?·…'.includes(char)) return 180
    return 22 + Math.random() * 40
  }

  async function stream(text, id) {
    display = ''
    for (let i = 0; i < text.length; i += 1) {
      if (id !== runId) return
      display += text[i]
      requestScroll()
      await sleep(delayFor(text[i]))
    }
    if (id !== runId) return
    streaming = false
    updatedAt = nowLabel()
  }

  async function pushLiveReport() {
    clearTimeout(liveTimer)
    clearTimeout(revertTimer)
    const id = (runId += 1)
    mode = 'live'
    userQuestion = ''
    streaming = true
    display = ''

    const { serverIp, apiPort } = loadServerConfig()
    const result = await window.llmAPI?.get(serverIp, apiPort)

    if (id !== runId) return

    if (!result?.response) {
      liveTimer = setTimeout(() => {
        if (mode === 'live') pushLiveReport()
      }, 5000)
      return
    }

    await stream(result.response, id)
    if (id !== runId) return

    liveTimer = setTimeout(() => {
      if (mode === 'live') pushLiveReport()
    }, LIVE_INTERVAL_MS)
  }

  async function answerQuestion(text) {
    clearTimeout(liveTimer)
    clearTimeout(revertTimer)
    const id = (runId += 1)
    mode = 'answer'
    userQuestion = text
    streaming = true
    display = ''

    const { serverIp, apiPort } = loadServerConfig()
    const result = await window.llmAPI?.ask(serverIp, apiPort, text)

    if (id !== runId) return

    const response = result?.response || '응답을 가져오지 못했습니다.'
    await stream(response, id)
    if (id !== runId) return

    revertTimer = setTimeout(pushLiveReport, 9000)
  }

  function handleSubmit() {
    const text = question.trim()
    if (!text) return
    question = ''
    lastQuestion = text
    answerQuestion(text)
  }

  function handleRetry() {
    spinning = true
    if (mode === 'answer' && lastQuestion) answerQuestion(lastQuestion)
    else pushLiveReport()
  }

  onMount(pushLiveReport)

  onDestroy(() => {
    clearTimeout(liveTimer)
    clearTimeout(revertTimer)
    runId += 1
  })
</script>

<section class="right-bottom">
  <header class="head">
    {#if mode === 'live'}
      <span class="status live"><span class="pulse"></span>실시간 분석</span>
      <span class="meta">{streaming ? '센서 데이터 갱신 중…' : `${updatedAt} 기준`}</span>
    {:else}
      <span class="status answer">질문 답변</span>
      <span class="meta">곧 실시간 분석으로 돌아갑니다</span>
    {/if}
  </header>

  <div class="body" bind:this={chatBody}>
    {#if mode === 'answer' && userQuestion}
      <div class="row user">
        <div class="bubble">{userQuestion}</div>
      </div>
    {/if}

    <div class="row assistant">
      <div class="avatar" aria-hidden="true">
        <svg viewBox="4 1.25 16 16" width="15" height="15" fill="none">
          <path
            d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4L12 3z"
            fill="currentColor"
          />
        </svg>
      </div>
      <div class="bubble">
        {#if streaming && display === ''}
          <span class="dots"><span></span><span></span><span></span></span>
        {:else}
          {@html renderMarkdown(display)}{#if streaming}<span class="cursor"></span>{/if}
        {/if}
      </div>
    </div>
  </div>

  <div class="composer">
    <input
      class="prompt"
      type="text"
      placeholder="궁금한 정보를 입력해주세요"
      bind:value={question}
      onkeydown={(event) => event.key === 'Enter' && handleSubmit()}
    />
    <button class="retry" type="button" onclick={handleRetry} aria-label="다시 시도하기">
      <svg
        class="icon"
        class:spin={spinning}
        viewBox="0 -1 24 24"
        width="18"
        height="18"
        fill="none"
        aria-hidden="true"
        onanimationend={() => (spinning = false)}
      >
        <path
          d="M20 11a8 8 0 1 0-2.34 5.66"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        />
        <path
          d="M20 4v6h-6"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  </div>
</section>

<style>
  .right-bottom {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 18px 16px;
    border-radius: 20px;
    border: 1px solid rgba(17, 24, 39, 0.04);
    background: #ffffff;
    box-shadow: 0 4px 16px rgba(17, 24, 39, 0.06);
    min-height: 0;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 700;
  }

  .status.live {
    color: #15b886;
  }

  .status.answer {
    color: #3182f6;
    padding: 4px 10px;
    border-radius: 999px;
    background: #e8f1ff;
  }

  .pulse {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #15b886;
    animation: pulse 1.8s infinite;
  }

  @keyframes pulse {
    0% {
      box-shadow: 0 0 0 0 rgba(21, 184, 134, 0.45);
    }
    70% {
      box-shadow: 0 0 0 7px rgba(21, 184, 134, 0);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(21, 184, 134, 0);
    }
  }

  .meta {
    font-size: 11px;
    font-weight: 600;
    color: #b0b8c1;
  }

  .body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-right: 4px;
  }

  .body::-webkit-scrollbar {
    width: 6px;
  }

  .body::-webkit-scrollbar-thumb {
    border-radius: 999px;
    background: #e5e8eb;
  }

  .row {
    display: flex;
    gap: 8px;
    align-items: flex-end;
  }

  .row.user {
    justify-content: flex-end;
  }

  .row.assistant {
    justify-content: flex-start;
  }

  .avatar {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    flex-shrink: 0;
    border-radius: 50%;
    background: linear-gradient(135deg, #3182f6, #6aa8ff);
    color: #ffffff;
    box-shadow: 0 2px 6px rgba(49, 130, 246, 0.32);
  }

  .bubble {
    max-width: 80%;
    padding: 10px 14px;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.62;
    border-radius: 16px;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .user .bubble {
    background: #3182f6;
    color: #ffffff;
    border-bottom-right-radius: 6px;
  }

  .assistant .bubble {
    background: #f2f4f6;
    color: #191f28;
    border-bottom-left-radius: 6px;
  }

  .dots {
    display: inline-flex;
    gap: 4px;
    padding: 4px 2px;
  }

  .dots span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #b0b8c1;
    animation: blink 1.2s infinite ease-in-out;
  }

  .dots span:nth-child(2) {
    animation-delay: 0.18s;
  }

  .dots span:nth-child(3) {
    animation-delay: 0.36s;
  }

  @keyframes blink {
    0%,
    80%,
    100% {
      opacity: 0.3;
      transform: translateY(0);
    }
    40% {
      opacity: 1;
      transform: translateY(-3px);
    }
  }

  .cursor {
    display: inline-block;
    width: 7px;
    height: 14px;
    margin-left: 2px;
    vertical-align: -2px;
    border-radius: 2px;
    background: #3182f6;
    animation: caret 1s steps(1) infinite;
  }

  @keyframes caret {
    0%,
    50% {
      opacity: 1;
    }
    50.01%,
    100% {
      opacity: 0;
    }
  }

  .composer {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .prompt {
    flex: 1;
    height: 44px;
    padding: 0 16px;
    border-radius: 999px;
    border: 1px solid #e5e8eb;
    background: #f9fafb;
    font-family: inherit;
    font-size: 14px;
    font-weight: 600;
    color: #191f28;
    outline: none;
    transition: border-color 0.12s ease, background 0.12s ease;
  }

  .prompt::placeholder {
    color: #8b95a1;
    font-weight: 600;
  }

  .prompt:focus {
    border-color: #3182f6;
    background: #ffffff;
  }

  .retry {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    flex-shrink: 0;
    border-radius: 50%;
    border: 1px solid #e5e8eb;
    background: #ffffff;
    color: #4e5968;
    cursor: pointer;
    transition: transform 0.12s ease, border-color 0.12s ease,
      background 0.12s ease, color 0.12s ease;
  }

  .retry:hover {
    transform: translateY(-1px);
    border-color: transparent;
    background: #f2f4f6;
    color: #4e5968;
  }

  .retry:active {
    transform: translateY(0);
  }

  .icon {
    transform-origin: 50% 50%;
  }

  .icon.spin {
    animation: spin 0.5s ease;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
</style>
