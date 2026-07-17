import { useEffect, useRef } from 'react'

// 轻量富文本编辑器：contentEditable + execCommand 工具栏（加粗/斜体/下划线/标题/列表/链接）
export default function RichText({ value, onChange }) {
  const ref = useRef(null)

  useEffect(() => {
    if (ref.current && ref.current.innerHTML !== (value || '')) {
      ref.current.innerHTML = value || ''
    }
  }, [value])

  const emit = () => onChange(ref.current.innerHTML)

  const exec = (cmd, arg) => {
    document.execCommand(cmd, false, arg || null)
    emit()
  }

  const addLink = () => {
    const url = window.prompt('输入链接地址：', 'https://')
    if (url) exec('createLink', url)
  }

  const stop = (e) => e.preventDefault()

  return (
    <>
      <div className="editor-toolbar">
        <button type="button" title="加粗" onMouseDown={stop} onClick={() => exec('bold')}>
          <b>B</b>
        </button>
        <button type="button" title="斜体" onMouseDown={stop} onClick={() => exec('italic')}>
          <i>I</i>
        </button>
        <button type="button" title="下划线" onMouseDown={stop} onClick={() => exec('underline')}>
          <u>U</u>
        </button>
        <button type="button" title="标题" onMouseDown={stop} onClick={() => exec('formatBlock', 'H2')}>
          H
        </button>
        <button type="button" title="无序列表" onMouseDown={stop} onClick={() => exec('insertUnorderedList')}>
          • 列表
        </button>
        <button type="button" title="有序列表" onMouseDown={stop} onClick={() => exec('insertOrderedList')}>
          1. 列表
        </button>
        <button type="button" title="插入链接" onMouseDown={stop} onClick={addLink}>
          🔗 链接
        </button>
      </div>
      <div
        className="rte"
        contentEditable
        suppressContentEditableWarning
        ref={ref}
        data-placeholder="输入知识内容，支持加粗、列表、链接等富文本格式…"
        onInput={emit}
      />
    </>
  )
}
