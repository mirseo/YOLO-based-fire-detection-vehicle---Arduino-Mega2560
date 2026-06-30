<script>
  import LeftPanel from './modules/LeftPanel.svelte'
  import RightTop from './modules/RightTop.svelte'
  import RightBottom from './modules/RightBottom.svelte'
  import Login from './modules/Login.svelte'
  import { session } from './state/session.svelte.js'
</script>

{#if session.authenticated}
  <div class="layout">
    <LeftPanel />
    <div class="right">
      <RightTop />
      <RightBottom />
    </div>
  </div>
{:else}
  <Login />
{/if}

<style>
  .layout {
    display: flex;
    gap: 16px;
    padding: 16px;
    height: 100vh;
    background: #f2f4f6;
  }

  .right {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
</style>
