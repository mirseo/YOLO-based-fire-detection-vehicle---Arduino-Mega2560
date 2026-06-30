const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('authAPI', {
  verifyPassword: (password) => ipcRenderer.invoke('auth:verify-password', password),
})

contextBridge.exposeInMainWorld('fileAPI', {
  saveCsv: (filename, content) => ipcRenderer.invoke('data:save-csv', filename, content),
})

contextBridge.exposeInMainWorld('sensorAPI', {
  getSensors: (serverIp, apiPort) => ipcRenderer.invoke('sensor:get', serverIp, apiPort),
})

contextBridge.exposeInMainWorld('llmAPI', {
  get: (serverIp, apiPort) => ipcRenderer.invoke('llm:get', serverIp, apiPort),
  ask: (serverIp, apiPort, question) => ipcRenderer.invoke('llm:ask', serverIp, apiPort, question),
})
