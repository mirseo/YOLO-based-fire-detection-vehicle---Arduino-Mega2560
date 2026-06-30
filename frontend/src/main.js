import { mount } from 'svelte'
import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css'
import './app.css'
import App from './App.svelte'

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
