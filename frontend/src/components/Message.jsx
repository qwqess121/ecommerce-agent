export default function Message({ msg, onFeedback }) {
  if (msg.role === 'user') {
    return (
      <div className="msg user">
        <div className="avatar me">我</div>
        <div className="bubble">{msg.text}</div>
      </div>
    )
  }

  const intent = msg.intent || ''
  const copy = () => {
    const text = (msg.text || '').replace(/\s+/g, ' ').trim()
    if (navigator.clipboard) navigator.clipboard.writeText(text).catch(() => {})
  }
  return (
    <div className="msg bot">
      <div className="avatar bot">AI</div>
      <div>
        <div className="bubble">
          {msg.text}
          {msg.streaming && <span className="stream-caret" />}
        </div>

        <div className="msg-actions">
          <button className="mini" title="复制回答" onClick={copy}>⧉ 复制</button>
          {!msg.streaming && (
            <>
              <button
                className={`mini ${msg.feedback === 'up' ? 'on' : ''}`}
                title="有帮助"
                onClick={() => onFeedback && onFeedback('up')}
              >
                👍
              </button>
              <button
                className={`mini ${msg.feedback === 'down' ? 'on' : ''}`}
                title="没帮助"
                onClick={() => onFeedback && onFeedback('down')}
              >
                👎
              </button>
            </>
          )}
        </div>

        {intent && (
          <div className="meta">
            <span className={`tag ${intent}`}>意图 · {intent}</span>
            {msg.feedback && (
              <span className={`fb ${msg.feedback}`}>
                {msg.feedback === 'up' ? '已赞' : '已踩'}
              </span>
            )}
          </div>
        )}

        {msg.sources && msg.sources.length > 0 && (
          <>
            <div
              className="src-toggle"
              onClick={(e) => e.currentTarget.nextElementSibling.classList.toggle('open')}
            >
              📎 参考来源（{msg.sources.length}）
            </div>
            <div className="sources">
              {msg.sources.map((s, i) => (
                <div className="src" key={i}>
                  <div className="src-name">
                    <span className="dot" />
                    {s.source || '知识库'}
                  </div>
                  <div className="src-snip">{s.snippet}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {msg.transfer && <div className="handoff">⚠️ 已为你转接人工客服，请稍候。</div>}
      </div>
    </div>
  )
}
