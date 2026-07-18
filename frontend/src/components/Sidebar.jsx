import Logo from './Logo'

export default function Sidebar({
  sessions,
  currentId,
  onSelect,
  onNew,
  onDelete,
  stats,
  onOpenKb,
  onExport,
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Logo size={40} className="logo" />
        <div>
          <div className="title">WHZ 智能客服</div>
          <div className="sub">WHZ Smart Care · RAG + Agent</div>
        </div>
      </div>

      <button className="btn btn-primary btn-block" onClick={onNew}>
        ＋ 新建对话
      </button>

      <button className="btn btn-sm btn-block" onClick={onExport} title="导出当前对话为 Markdown">
        ⬇ 导出对话
      </button>

      <div className="sessions-head">
        <span>历史对话</span>
        <span>{sessions.length}</span>
      </div>
      <div className="sessions">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`session ${s.id === currentId ? 'active' : ''}`}
            onClick={() => onSelect(s.id)}
          >
            <span className="label">{s.title || '新对话'}</span>
            <span
              className="del"
              title="删除"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(s.id)
              }}
            >
              ×
            </span>
          </div>
        ))}
      </div>

      <div className="kb-card">
        <h4>📚 知识库</h4>
        <div className="kb-stat">
          已索引 <b>{stats?.chunks ?? '-'}</b> 个知识块
          {stats?.user_entries ? (
            <>
              <br />
              其中用户条目 <b>{stats.user_entries}</b> 条
            </>
          ) : null}
          <br />
          {stats?.vector_enabled ? '向量检索已启用' : '仅关键词检索'}
        </div>
        <div className="kb-actions">
          <button className="btn btn-sm btn-block" onClick={onOpenKb}>
            管理知识库
          </button>
        </div>
      </div>
    </aside>
  )
}
