<script>
  import { fly } from 'svelte/transition'

  let { open = false, message = '', tone = 'success', persistent = false, onclose } = $props()

  let timer

  $effect(() => {
    if (open && !persistent) {
      clearTimeout(timer)
      timer = setTimeout(() => onclose?.(), 2500)
    }
  })
</script>

{#if open}
  <div class="anchor">
    <div class="toast toast-{tone}" transition:fly={{ y: -16, duration: 250 }}>
      <span class="icon">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
          <path
            d={tone === 'error' ? 'M6 6L18 18M18 6L6 18' : 'M5 12.5L10 17.5L19 7'}
            stroke="#ffffff"
            stroke-width="2.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
      <span>{message}</span>
    </div>
  </div>
{/if}

<style>
  .anchor {
    position: fixed;
    top: 20px;
    left: 0;
    right: 0;
    z-index: 200;
    display: flex;
    justify-content: center;
    pointer-events: none;
  }

  .toast {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px 10px 10px;
    border-radius: 14px;
    border: 1px solid rgba(17, 24, 39, 0.04);
    background: #ffffff;
    color: #191f28;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.01em;
    box-shadow: 0 8px 24px rgba(17, 24, 39, 0.12);
  }

  .icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 999px;
  }

  .toast-success .icon {
    background: #3182f6;
  }

  .toast-error .icon {
    background: #f04452;
  }
</style>
