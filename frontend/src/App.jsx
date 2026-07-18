import { useEffect, useRef, useState } from 'react'
import Logo from './components/Logo'
import Sidebar from './components/Sidebar'
import Composer from './components/Composer'
import Message from './components/Message'
import Knowledge from './components/Knowledge'
import { getInitialTheme, applyTheme } from './theme'
import * as api from './api'

const genId = () => 'm_' + Math.random().toString(36).slice(2) + Date.now().toString(36)
const STORE_KEY = 'whz_sessions'
const CUR_KEY = 'whz_current'

const SUGGESTIONS = [
  '如何申请退货？',
  '查询订单 123456',
  '运费怎么算',
  '怎么开发票',
  '转人工',
]

export default function App() {
  // ---- 主题 ----
  const [theme, setTheme] = useState(getInitialTheme())
  useEffect(() => {
    applyTheme(theme)
  }, [theme])
  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  // ---- 会话 ----
  const [sessions, setSessions] = useState([])
  const [currentId, setCurrentId] = useState(null)
  const [draft, setDraft] = useState('')
  const [mode, setMode] = useState('…')
  const [connError, setConnError] = useState(false)

  // ---- 知识库 ----
  const [kbOpen, setKbOpen] = useState(false)
  const [entries, setEntries] = useState([])
  const [kbLoading, setKbLoading] = useState(false)
  const [stats, setStats] = useState(null)

  // ---- 语音 ----
  const [micSupported, setMicSupported] = useState(false)
  const [micState, setMicState] = useState('off')
  const recRef = useRef(null)
  const msgsRef = useRef(null)

  // 初始化会话
  useEffect(() => {
    let saved = []
    try {
      saved = JSON.parse(localStorage.getItem(STORE_KEY) || '[]')
    } catch {
      saved = []
    }
    let cur = localStorage.getItem(CUR_KEY)
    if (!saved.length) {
      const s = { id: genId(), title: '新对话', messages: [] }
      saved = [s]
      cur = s.id
    }
    if (!saved.find((s) => s.id === cur)) cur = saved[0].id
    setSessions(saved)
    setCurrentId(cur)
    // eslint-disable-next-line
  }, [])

  // 持久化
  useEffect(() => {
    if (sessions.length) localStorage.setItem(STORE_KEY, JSON.stringify(sessions))
  }, [sessions])
  useEffect(() => {
    if (currentId) localStorage.setItem(CUR_KEY, currentId)
  }, [currentId])

  // 健康检查 + 连接状态
  useEffect(() => {
    api
      .getHealth()
      .then((d) => {
        setMode(d.mock ? '演示模式 (Mock)' : '真实大模型')
        setStats(d.store)
        setConnError(false)
      })
      .catch(() => setConnError(true))
  }, [])

  // 语音支持检测
  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    setMicSupported(!!SR)
  }, [])

  // 自动滚动到底部
  useEffect(() => {
    const el = msgsRef.current
    if (el) el.scrollTop = el.scrollHeight
  })

  const current = sessions.find((s) => s.id === currentId) || sessions[0]

  // ---- 会话操作 ----
  const createSession = () => {
    const s = { id: genId(), title: '新对话', messages: [] }
    setSessions((prev) => [s, ...prev])
    setCurrentId(s.id)
  }
  const selectSession = (id) => setCurrentId(id)
  const deleteSession = (id) => {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id)
      if (!next.length) {
        const s = { id: genId(), title: '新对话', messages: [] }
        setCurrentId(s.id)
        return [s]
      }
      if (id === currentId) setCurrentId(next[0].id)
      return next
    })
  }

  const patchMsg = (sid, mid, patch) => {
    setSessions((prev) =>
      prev.map((s) =>
        s.id === sid
          ? {
              ...s,
              messages: s.messages.map((m) =>
                m.id === mid ? (typeof patch === 'function' ? patch(m) : { ...m, ...patch }) : m
              ),
            }
          : s
      )
    )
  }

  const sendMessage = async (text) => {
    const t = (text || '').trim()
    if (!t) return
    const sid = currentId
    if (!sid) return
    const uid = genId()
    const aid = genId()
    const userMsg = { id: uid, role: 'user', text: t }
    const botMsg = { id: aid, role: 'assistant', text: '', intent: '', sources: [], transfer: false, streaming: true, feedback: null }
    setSessions((prev) =>
      prev.map((s) =>
        s.id === sid
          ? {
              ...s,
              title: s.messages.length ? s.title : t.slice(0, 16),
              messages: [...s.messages, userMsg, botMsg],
            }
          : s
      )
    )
    await api.chatStream(sid, t, {
      onMeta: (meta) =>
        patchMsg(sid, aid, {
          intent: meta.intent,
          sources: meta.sources,
          transfer: meta.transfer,
        }),
      onDelta: (d) => patchMsg(sid, aid, (m) => ({ ...m, text: m.text + d })),
      onError: (err) => {
        setConnError(true)
        patchMsg(sid, aid, {
          text: '⚠️ 调用后端失败：' + err.message + '（请确认后端已启动，并通过其地址打开本页面）',
          streaming: false,
        })
      },
      onDone: () => patchMsg(sid, aid, { streaming: false }),
    })
  }

  const resetCurrent = async () => {
    if (!current) return
    setSessions((prev) => prev.map((s) => (s.id === current.id ? { ...s, messages: [] } : s)))
    try {
      await api.resetSession(current.id)
    } catch {
      /* ignore */
    }
  }

  // ---- 语音输入 ----
  const toggleMic = () => {
    if (!micSupported) return
    if (micState === 'on') {
      recRef.current?.stop()
      return
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang = 'zh-CN'
    rec.interimResults = true
    rec.onresult = (e) => {
      let t = ''
      for (let i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript
      setDraft(t)
    }
    rec.onend = () => setMicState('off')
    rec.onerror = () => setMicState('off')
    recRef.current = rec
    try {
      rec.start()
      setMicState('on')
    } catch {
      setMicState('off')
    }
  }

  // ---- 知识库操作 ----
  const refreshEntries = async () => {
    setKbLoading(true)
    try {
      const d = await api.getEntries()
      setEntries(d.entries || [])
    } catch {
      /* ignore */
    } finally {
      setKbLoading(false)
    }
  }
  const refreshStats = async () => {
    try {
      const s = await api.getStats()
      setStats(s)
    } catch {
      /* ignore */
    }
  }
  const openKb = () => {
    setKbOpen(true)
    refreshEntries()
  }
  const onAdd = async (title, html) => {
    await api.addEntry(title, html)
    await refreshEntries()
    await refreshStats()
  }
  const onEdit = async (id, title, html) => {
    await api.updateEntry(id, title, html)
    await refreshEntries()
  }
  const onDelete = async (id) => {
    await api.deleteEntry(id)
    await refreshEntries()
    await refreshStats()
  }
  const onUpload = async (file, onProgress) => {
    await api.uploadFile(file, onProgress)
    await refreshEntries()
    await refreshStats()
  }

  // 消息反馈（赞/踩）
  const onFeedback = (mid, val) => {
    const sid = currentId
    if (!sid) return
    patchMsg(sid, mid, { feedback: val })
  }

  // 导出当前对话为 Markdown
  const exportCurrent = () => {
    if (!current || !current.messages.length) return
    const lines = [`# ${current.title || 'WHZ 智能客服对话'}`, '']
    for (const m of current.messages) {
      if (m.role === 'user') lines.push(`**用户**：${m.text}`)
      else lines.push(`**WHZ 智能客服**：${m.text}`)
      lines.push('')
    }
    lines.push('---', `_导出时间：${new Date().toLocaleString()}_`)
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `whz-对话-${(current.title || 'chat').slice(0, 12)}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const openKbFromSidebar = openKb

  return (
    <div className="app">
      {connError && (
        <div className="conn-banner show">
          <span
            className="x"
            onClick={() => setConnError(false)}
          >
            ×
          </span>
          ⚠️ <b>无法连接到后端服务</b>：请确认后端已启动，并通过后端地址打开本页面（例如{' '}
          <code>http://127.0.0.1:8000/ui/</code>），不要通过文件预览/独立标签页打开。
        </div>
      )}

      <Sidebar
        sessions={sessions}
        currentId={currentId}
        onSelect={selectSession}
        onNew={createSession}
        onDelete={deleteSession}
        stats={stats}
        onOpenKb={openKbFromSidebar}
        onExport={exportCurrent}
      />

      <main className="main">
        <div className="topbar">
          <div className="topbar-left">
            <span className="conv-title">{current?.title || '新对话'}</span>
            <span className={`badge ${mode.includes('真实') ? 'real' : ''}`}>{mode}</span>
          </div>
          <div className="topbar-right">
            <button className="btn btn-sm" onClick={openKbFromSidebar}>
              📚 知识库
            </button>
            <button className="btn btn-sm" onClick={resetCurrent}>
              🗑 清空
            </button>
            <button className="icon-btn" onClick={toggleTheme} title="切换深色/浅色模式">
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
          </div>
        </div>

        <div className="messages" ref={msgsRef}>
          <div className="messages-inner">
            {!current || current.messages.length === 0 ? (
              <div className="welcome">
                <Logo size={68} className="welcome-logo" />
                <h2>你好，我是 WHZ 智能客服</h2>
                <p>我可以回答商品、订单、退换货、物流等问题，也能帮你查询订单与物流。试试下面的问题：</p>
                <div className="chips">
                  {SUGGESTIONS.map((s) => (
                    <div className="chip" key={s} onClick={() => sendMessage(s)}>
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              current.messages.map((m) => (
                <Message key={m.id} msg={m} onFeedback={(v) => onFeedback(m.id, v)} />
              ))
            )}
          </div>
        </div>

        <Composer
          text={draft}
          setText={setDraft}
          onSend={sendMessage}
          disabled={false}
          micState={micState}
          onToggleMic={toggleMic}
          micSupported={micSupported}
        />
      </main>

      <Knowledge
        open={kbOpen}
        onClose={() => setKbOpen(false)}
        entries={entries}
        loading={kbLoading}
        onAdd={onAdd}
        onEdit={onEdit}
        onDelete={onDelete}
        onUpload={onUpload}
      />
    </div>
  )
}
