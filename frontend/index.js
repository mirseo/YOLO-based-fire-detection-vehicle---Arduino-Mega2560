const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const http = require('http')
const { spawn } = require('child_process')
const os = require('os')
const { loadEnv } = require('./electron/env')
const { verifyPassword } = require('./electron/auth')

const isDev = process.argv.includes('--dev')
const DEV_SERVER_URL = 'http://localhost:5173'

let mainWindow = null

loadEnv()

function isAllowedNavigation(targetUrl) {
  try {
    const target = new URL(targetUrl)
    if (isDev) return target.origin === new URL(DEV_SERVER_URL).origin
    return target.protocol === 'file:'
  } catch {
    return false
  }
}

function registerAuthIpc() {
  ipcMain.handle('auth:verify-password', (event, password) => {
    if (typeof password !== 'string' || password.length > 256) {
      return { ok: false, message: '비밀번호를 확인해 주세요' }
    }
    try {
      return verifyPassword(password)
    } catch (error) {
      console.error('[auth] verify-password failed:', error && error.message)
      return { ok: false, message: '로그인을 처리하지 못했어요. 잠시 후 다시 시도해 주세요' }
    }
  })
}

function registerSensorIpc() {
  ipcMain.handle('sensor:get', (event, serverIp, apiPort) => {
    if (typeof serverIp !== 'string' || !Number.isFinite(apiPort)) return null
    return new Promise((resolve) => {
      const req = http.get(
        { hostname: serverIp, port: apiPort, path: '/api/sensors', timeout: 2000 },
        (res) => {
          let body = ''
          res.on('data', (chunk) => { body += chunk })
          res.on('end', () => {
            try { resolve(JSON.parse(body)) }
            catch { resolve(null) }
          })
        }
      )
      req.on('error', () => resolve(null))
      req.on('timeout', () => { req.destroy(); resolve(null) })
    })
  })
}

const LLM_ASK_SYSTEM_PROMPT =
  '당신은 화재 현장 로봇의 상황 분석 AI입니다. ' +
  '센서 데이터, YOLO 탐지 결과, 이전 분석 내용을 참고해 사용자 질문에 간결하고 명확하게 답변합니다. ' +
  '형식 제약 없이 자연스럽게 답변하세요.'

const LLM_SYSTEM_PROMPT =
  '당신은 화재 현장 로봇의 실시간 상황 분석 AI입니다. ' +
  '센서 데이터와 YOLO 탐지 결과를 바탕으로 간결하고 명확한 상황 분석을 제공합니다.\n\n' +
  '반드시 아래 세 줄 형식으로만 응답하십시오. 형식 외의 어떠한 텍스트도 출력하지 마십시오.\n\n' +
  '(인식) [YOLO 탐지 결과와 센서 이상 징후를 한 문장으로 요약]\n' +
  '(분석) [현재 상황의 위험도와 원인을 한 문장으로 판단]\n' +
  '(조언) [로봇 운용자에게 권장하는 행동을 한 문장으로 제시]\n\n' +
  '예시:\n' +
  '(인식) 1층 복도에서 생존자 1명 감지(87% 신뢰), 온도 42°C\n' +
  '(분석) 온도 센서 42°C로 화재 위험 구역 추정\n' +
  '(조언) 우회 경로로 접근 권장'

function httpGetJson(hostname, port, urlPath, timeout) {
  return new Promise((resolve) => {
    const req = http.get(
      { hostname, port, path: urlPath, timeout },
      (res) => {
        let body = ''
        res.on('data', (chunk) => { body += chunk })
        res.on('end', () => {
          try { resolve(JSON.parse(body)) }
          catch { resolve(null) }
        })
      }
    )
    req.on('error', () => resolve(null))
    req.on('timeout', () => { req.destroy(); resolve(null) })
  })
}

async function buildLlmContext(serverIp, apiPort) {
  const [sensors, yolos] = await Promise.all([
    httpGetJson(serverIp, apiPort, '/api/sensors', 2000),
    httpGetJson(serverIp, apiPort, '/api/yolos', 2000),
  ])
  const detections = Array.isArray(yolos?.detections) ? yolos.detections : []
  const hasData = detections.length > 0 || sensors !== null
  const detStr = detections.length
    ? detections.map((d) => `${d.label}(${Number(d.conf).toFixed(2)})`).join(', ')
    : '없음'
  const sensorStr = sensors
    ? Object.entries(sensors)
        .filter(([, v]) => typeof v === 'number')
        .map(([k, v]) => `${k}: ${v}`)
        .join(', ')
    : '없음'
  return { context: `탐지: ${detStr}\n센서: ${sensorStr}`, hasData }
}

function callClaude(userMessage, systemPrompt = LLM_SYSTEM_PROMPT) {
  return new Promise((resolve, reject) => {
    const fullPrompt = `${systemPrompt}\n\n${userMessage}`
    const tmpPath = path.join(os.tmpdir(), `llm-${Date.now()}.txt`)
    const cleanup = () => fs.unlink(tmpPath, () => {})

    try {
      fs.writeFileSync(tmpPath, fullPrompt, 'utf8')
    } catch (err) {
      return reject(err)
    }

    const proc = process.platform === 'win32'
      ? spawn('powershell', [
          '-NonInteractive', '-Command',
          `claude -p (Get-Content '${tmpPath}' -Raw -Encoding UTF8)`,
        ], { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
      : spawn('claude', ['-p', fullPrompt], { stdio: ['ignore', 'pipe', 'pipe'] })

    let stdout = ''
    let stderr = ''
    const timer = setTimeout(() => { proc.kill(); reject(new Error('타임아웃')) }, 60000)
    proc.stdout.on('data', (chunk) => { stdout += chunk.toString() })
    proc.stderr.on('data', (chunk) => { stderr += chunk.toString() })
    proc.on('close', (code) => {
      clearTimeout(timer)
      cleanup()
      if (code === 0 && stdout.trim()) return resolve(stdout.trim())
      console.error('[llm] claude failed code=%d stderr=%s', code, stderr.trim())
      reject(new Error(stderr.trim() || `종료 코드 ${code}`))
    })
    proc.on('error', (err) => { clearTimeout(timer); cleanup(); console.error('[llm] spawn error:', err.message); reject(err) })
  })
}

const llmDb = { lastResponse: null }

function registerLlmIpc() {
  ipcMain.handle('llm:get', async (event, serverIp, apiPort) => {
    if (typeof serverIp !== 'string' || !Number.isFinite(apiPort)) return null
    try {
      const { context, hasData } = await buildLlmContext(serverIp, apiPort)
      if (!hasData) return { response: '현재 상태는 안전합니다.' }
      const response = await callClaude(`현재 상황:\n${context}`)
      llmDb.lastResponse = response
      return { response }
    } catch (err) {
      console.error('[llm:get]', err.message)
      return { response: `(오류) ${err.message}` }
    }
  })

  ipcMain.handle('llm:ask', async (event, serverIp, apiPort, question) => {
    if (typeof serverIp !== 'string' || !Number.isFinite(apiPort) || typeof question !== 'string') return null
    const previousAnalysis = llmDb.lastResponse
    llmDb.lastResponse = null
    try {
      const { context } = await buildLlmContext(serverIp, apiPort)
      const userMessage = previousAnalysis
        ? `현재 상황:\n${context}\n\n이전 분석 결과:\n${previousAnalysis}\n\n질문: ${question}`
        : `현재 상황:\n${context}\n\n질문: ${question}`
      const response = await callClaude(userMessage, LLM_ASK_SYSTEM_PROMPT)
      return { response }
    } catch (err) {
      console.error('[llm:ask]', err.message)
      return { response: `(오류) ${err.message}` }
    }
  })
}

function registerFileIpc() {
  ipcMain.handle('data:save-csv', async (event, filename, content) => {
    if (typeof filename !== 'string' || typeof content !== 'string') {
      return { ok: false }
    }
    const win = BrowserWindow.fromWebContents(event.sender)
    const { canceled, filePath } = await dialog.showSaveDialog(win, {
      defaultPath: filename,
      filters: [{ name: 'CSV', extensions: ['csv'] }],
    })
    if (canceled || !filePath) return { ok: false }
    try {
      await fs.promises.writeFile(filePath, content, 'utf8')
      return { ok: true, filePath }
    } catch (error) {
      console.error('[data] save-csv failed:', error && error.message)
      return { ok: false }
    }
  })
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 720,
    useContentSize: true,
    resizable: true,
    maximizable: true,
    fullscreenable: true,
    show: false,
    title: 'SEI',
    webPreferences: {
      preload: path.join(__dirname, 'electron', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow = win
  win.on('closed', () => { mainWindow = null })

  win.once('ready-to-show', () => win.show())

  win.setAspectRatio(16 / 9)

  win.on('page-title-updated', (e) => e.preventDefault())
  win.setMenuBarVisibility(false)

  win.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedNavigation(url)) event.preventDefault()
  })

  win.webContents.on('will-redirect', (event, url) => {
    if (!isAllowedNavigation(url)) event.preventDefault()
  })

  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))

  if (isDev) {
    win.loadURL(DEV_SERVER_URL)
  } else {
    win.loadFile(path.join(__dirname, 'dist', 'index.html'))
  }
}

const gotSingleInstanceLock = app.requestSingleInstanceLock()

if (!gotSingleInstanceLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })

  app.whenReady().then(() => {
    registerAuthIpc()
    registerFileIpc()
    registerSensorIpc()
    registerLlmIpc()
    createWindow()

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
  })
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
