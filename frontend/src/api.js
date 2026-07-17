// 与后端通信的封装：同源（由 FastAPI 托管），路径直接以 / 开头即可。

export async function getHealth() {
  const r = await fetch('/health')
  if (!r.ok) throw new Error('health ' + r.status)
  return r.json()
}

export async function getStats() {
  const r = await fetch('/kb_stats')
  return r.json()
}

export async function getEntries() {
  const r = await fetch('/kb/entries')
  if (!r.ok) throw new Error('entries ' + r.status)
  return r.json()
}

export async function addEntry(title, html) {
  const r = await fetch('/kb/entries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, html }),
  })
  if (!r.ok) throw new Error('add ' + r.status)
  return r.json()
}

export async function updateEntry(id, title, html) {
  const r = await fetch('/kb/entries/' + encodeURIComponent(id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, html }),
  })
  if (!r.ok) throw new Error('update ' + r.status)
  return r.json()
}

export async function deleteEntry(id) {
  const r = await fetch('/kb/entries/' + encodeURIComponent(id), { method: 'DELETE' })
  if (!r.ok) throw new Error('delete ' + r.status)
  return r.json()
}

export async function resetSession(sessionId) {
  await fetch('/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
}

// SSE 流式对话：逐块回调 meta / delta / done
export async function chatStream(sessionId, message, handlers) {
  const { onMeta, onDelta, onDone, onError } = handlers || {}
  try {
    const res = await fetch('/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message }),
    })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const raw = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const ev = parseEvent(raw)
        if (!ev) continue
        if (ev.event === 'meta' && onMeta) onMeta(ev.data)
        else if (ev.event === 'delta' && onDelta) onDelta(ev.data)
        else if (ev.event === 'done' && onDone) onDone()
      }
    }
    if (onDone) onDone()
  } catch (e) {
    if (onError) onError(e)
  }
}

function parseEvent(raw) {
  let event = 'message'
  let data = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  try {
    data = JSON.parse(data)
  } catch {
    /* keep as string */
  }
  return { event, data }
}

// 上传文件并显示进度（XHR upload 事件）
export function uploadFile(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const fd = new FormData()
    fd.append('file', file)
    xhr.open('POST', '/kb/upload')
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch {
          resolve({})
        }
      } else reject(new Error('上传失败：' + xhr.status))
    }
    xhr.onerror = () => reject(new Error('网络错误，上传失败'))
    xhr.send(fd)
  })
}
