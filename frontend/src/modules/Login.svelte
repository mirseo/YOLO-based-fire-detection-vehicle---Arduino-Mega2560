<script>
  import { config } from '../config/config.js'
  import { session } from '../state/session.svelte.js'

  let password = $state('')
  let showPassword = $state(false)
  let error = $state('')
  let loading = $state(false)

  const canSubmit = $derived(password.length > 0 && !loading)

  async function verifyPassword(value) {
    if (window.authAPI) {
      return window.authAPI.verifyPassword(value)
    }
    if (import.meta.env.DEV) {
      const expected = import.meta.env.VITE_AUTH_PASSWORD
      if (!expected) {
        return { ok: false, message: '인증 서비스를 사용할 수 없어요' }
      }
      if (value !== expected) {
        return { ok: false, message: '비밀번호가 일치하지 않아요' }
      }
      return { ok: true }
    }
    return { ok: false, message: '인증 서비스를 사용할 수 없어요' }
  }

  async function login() {
    if (!canSubmit) return
    error = ''
    loading = true
    try {
      const result = await verifyPassword(password)
      if (!result.ok) {
        error = result.message || '비밀번호가 일치하지 않아요'
        return
      }
      session.open()
    } catch {
      error = '로그인을 처리하지 못했어요. 잠시 후 다시 시도해 주세요'
    } finally {
      loading = false
    }
  }

  function autofocus(node) {
    node.focus()
  }
</script>

<div class="page">
  <div class="card">
      <span class="badge">{config.systemName}</span>
      <div class="head">
        <h1>비밀번호로 로그인</h1>
        <p>비밀번호를 입력해 로봇 제어 시스템에 접속하세요</p>
      </div>

      <div class="field">
        <label for="password">비밀번호</label>
        <div class="password">
          <input
            id="password"
            type={showPassword ? 'text' : 'password'}
            autocomplete="current-password"
            placeholder="비밀번호를 입력해 주세요"
            class:invalid={error}
            bind:value={password}
            oninput={() => (error = '')}
            onkeydown={(e) => e.key === 'Enter' && login()}
            use:autofocus
          />
          <button
            type="button"
            class="toggle"
            aria-label={showPassword ? '비밀번호 숨기기' : '비밀번호 표시'}
            aria-pressed={showPassword}
            onclick={() => (showPassword = !showPassword)}
          >
            {#if showPassword}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path
                  d="M3 3L21 21"
                  stroke="#8b95a1"
                  stroke-width="2"
                  stroke-linecap="round"
                />
                <path
                  d="M10.6 5.1A11 11 0 0 1 12 5c6.5 0 10 7 10 7a18.4 18.4 0 0 1-3 4M6.6 6.6A18.4 18.4 0 0 0 2 12s3.5 7 10 7c1.5 0 2.9-.3 4.1-.8"
                  stroke="#8b95a1"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
                <path
                  d="M9.9 9.9A3 3 0 0 0 14.1 14.1"
                  stroke="#8b95a1"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            {:else}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path
                  d="M2 12S5.5 5 12 5s10 7 10 7-3.5 7-10 7-10-7-10-7Z"
                  stroke="#8b95a1"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
                <circle cx="12" cy="12" r="3" stroke="#8b95a1" stroke-width="2" />
              </svg>
            {/if}
          </button>
        </div>
        {#if error}
          <span class="error">{error}</span>
        {/if}
      </div>

      <button class="primary" disabled={!canSubmit} onclick={login}>
        {loading ? '로그인 중...' : '로그인'}
      </button>
  </div>
</div>

<style>
  .page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 24px;
    background: linear-gradient(158deg, #ffffff 0%, #f6f8fa 48%, #eef1f4 100%);
  }

  .card {
    width: 100%;
    max-width: 400px;
    display: flex;
    flex-direction: column;
    padding: 36px 28px 28px;
    background: #ffffff;
    border-radius: 28px;
    box-shadow: 0 12px 40px rgba(17, 24, 39, 0.08);
  }

  .badge {
    align-self: flex-start;
    padding: 6px 14px;
    border-radius: 999px;
    background: rgba(49, 130, 246, 0.1);
    color: #3182f6;
    font-size: 13px;
    font-weight: 700;
  }

  .head {
    margin: 20px 0 28px;
  }

  h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #191f28;
  }

  .head p {
    margin: 10px 0 0;
    font-size: 15px;
    line-height: 1.5;
    color: #8b95a1;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 24px;
  }

  label {
    font-size: 13px;
    font-weight: 600;
    color: #4e5968;
  }

  input {
    width: 100%;
    height: 56px;
    padding: 0 18px;
    border: 1px solid #e5e8eb;
    border-radius: 14px;
    background: #ffffff;
    font-size: 16px;
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

  .password {
    position: relative;
  }

  .password input {
    padding-right: 52px;
  }

  .toggle {
    position: absolute;
    top: 0;
    right: 0;
    width: 52px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    cursor: pointer;
  }

  .error {
    font-size: 13px;
    color: #f04452;
  }

  .primary {
    width: 100%;
    height: 56px;
    border: none;
    border-radius: 14px;
    background: #3182f6;
    color: #ffffff;
    font-size: 17px;
    font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .primary:hover:not(:disabled) {
    background: #1b64da;
  }

  .primary:disabled {
    background: #e8ebed;
    color: #b0b8c1;
    cursor: not-allowed;
  }
</style>
