import { useEffect, useRef } from 'react'

export default function Composer({ text, setText, onSend, disabled, micState, onToggleMic, micSupported }) {
  const ref = useRef(null)

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = 'auto'
      ref.current.style.height = Math.min(ref.current.scrollHeight, 160) + 'px'
    }
  }, [text])

  const send = () => {
    const t = text.trim()
    if (!t || disabled) return
    onSend(t)
    setText('')
  }

  return (
    <div className="composer">
      <div className="composer-inner">
        <div className="input-wrap">
          <textarea
            ref={ref}
            rows={1}
            placeholder="输入你的问题，Enter 发送，Shift+Enter 换行…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
          />
          <button
            className={`mic ${micState === 'on' ? 'listening' : ''} ${micSupported ? '' : 'disabled'}`}
            title={
              micSupported
                ? micState === 'on'
                  ? '停止语音输入'
                  : '语音输入（中文）'
                : '当前浏览器不支持语音输入'
            }
            disabled={!micSupported}
            onClick={onToggleMic}
          >
            🎤
          </button>
          <button className="send" onClick={send} disabled={disabled || !text.trim()}>
            ➤
          </button>
        </div>
        <div className="hint">
          由 RAG + 多智能体驱动 · 回答仅供参考，涉及账户与资金请以官方为准
        </div>
      </div>
    </div>
  )
}
