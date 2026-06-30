<script>
  let { connected = false } = $props()
</script>

<div class="status" class:connected>
  <span class="dot"></span>
  <span class="label">{connected ? '연결됨' : '연결 끊김'}</span>
</div>

<style>
  .status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 999px;
    background: rgba(240, 68, 82, 0.1);
    color: #f04452;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .status.connected {
    background: rgba(49, 130, 246, 0.1);
    color: #3182f6;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }
</style>
