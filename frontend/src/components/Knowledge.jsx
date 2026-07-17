import { useState, useRef } from 'react'
import RichText from './RichText'

// 知识库抽屉：上传（带进度）、条目列表、新增/编辑（富文本）
export default function Knowledge({
  open,
  onClose,
  entries,
  loading,
  onAdd,
  onEdit,
  onDelete,
  onUpload,
}) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [drag, setDrag] = useState(false)
  const [editing, setEditing] = useState(null) // {id?, title, html}
  const fileRef = useRef(null)

  if (!open) return null

  const doUpload = async (file) => {
    if (!file) return
    setUploading(true)
    setProgress(0)
    try {
      await onUpload(file, (p) => setProgress(p))
      setProgress(100)
    } catch (e) {
      window.alert('上传失败：' + e.message)
    } finally {
      setUploading(false)
      setTimeout(() => setProgress(0), 900)
    }
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer">
        <div className="drawer-head">
          <div>
            <h3>知识库管理</h3>
            <div className="sub">用户条目可编辑/删除 · 种子语料可移除</div>
          </div>
          <button className="icon-btn" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="drawer-body">
          <div className="kb-toolbar">
            <button className="btn btn-primary" onClick={() => setEditing({ title: '', html: '' })}>
              ＋ 新增知识
            </button>
          </div>

          <div
            className={`upload-box ${drag ? 'drag' : ''}`}
            onClick={() => !uploading && fileRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setDrag(true)
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDrag(false)
              doUpload(e.dataTransfer.files[0])
            }}
          >
            点击或拖拽文件到此处上传（.json / .jsonl / .txt / .md / .csv）
            {uploading && (
              <div className="progress">
                <div className="progress-bar" style={{ width: progress + '%' }} />
              </div>
            )}
            {uploading && <div className="upload-hint">上传中 {progress}% …</div>}
            <input
              ref={fileRef}
              type="file"
              accept=".json,.jsonl,.txt,.md,.csv"
              style={{ display: 'none' }}
              onChange={(e) => {
                doUpload(e.target.files[0])
                e.target.value = ''
              }}
            />
          </div>

          {loading ? (
            <div className="kb-empty">加载中…</div>
          ) : entries.length === 0 ? (
            <div className="kb-empty">暂无知识条目</div>
          ) : (
            <div className="entry-list">
              {entries.map((e) => (
                <div className="entry" key={e.id}>
                  <div className="entry-head">
                    <span className={`entry-kind ${e.kind}`}>{e.kind === 'user' ? '用户' : '种子'}</span>
                    <span className="entry-title" title={e.title}>
                      {e.title}
                    </span>
                  </div>
                  <div className="entry-snip">{e.snippet}</div>
                  <div className="entry-actions">
                    {e.kind === 'user' && (
                      <button
                        className="btn"
                        onClick={() => setEditing({ id: e.id, title: e.title, html: e.html || '' })}
                      >
                        编辑
                      </button>
                    )}
                    <button
                      className="btn entry-del"
                      onClick={() => {
                        if (window.confirm('确定删除该知识条目？')) onDelete(e.id)
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {editing && (
        <EditorModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={async (title, html) => {
            if (editing.id) await onEdit(editing.id, title, html)
            else await onAdd(title, html)
            setEditing(null)
          }}
        />
      )}
    </>
  )
}

function EditorModal({ initial, onClose, onSave }) {
  const [title, setTitle] = useState(initial.title || '')
  const [html, setHtml] = useState(initial.html || '')
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{initial.id ? '编辑知识' : '新增知识'}</h3>
          <button className="icon-btn" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <div className="field">
            <label>标题</label>
            <input
              className="title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="如：会员积分规则"
            />
          </div>
          <div className="field">
            <label>内容（富文本）</label>
            <RichText value={html} onChange={setHtml} />
          </div>
        </div>
        <div className="modal-foot">
          <button className="btn" onClick={onClose}>
            取消
          </button>
          <button
            className="btn btn-primary"
            disabled={!title.trim() && !html.trim()}
            onClick={() => onSave(title, html)}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  )
}
