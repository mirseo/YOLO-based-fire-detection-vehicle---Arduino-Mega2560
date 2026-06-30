const BOM = String.fromCharCode(0xfeff)

export async function saveCsv(filename, csv) {
  const content = BOM + csv

  if (window.fileAPI?.saveCsv) {
    return window.fileAPI.saveCsv(filename, content)
  }

  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
  return { ok: true }
}
