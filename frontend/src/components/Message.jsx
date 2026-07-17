export default function Message({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="msg user">
        <div className="avatar me">我</div>
        <div className="bubble">{msg.text}</div>
      </div>
    )
  }

  const intent = msg.intent || ''
  return (
    <div className="msg bot">
      <div className="avatar bot">AI</div>
      <div>
        <div className="bubble">
          {msg.text}
          {msg.streaming && <span className="stream-caret" />}
        </div>

        {intent && (
          <div className="meta">
            <span className={`tag ${intent}`}>意图 · {intent}</span>
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
