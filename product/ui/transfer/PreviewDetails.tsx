import { useEffect, useState } from 'react'
import {
  labels,
  describe,
  failure,
  type Changes,
  type Preview,
  type TransferRequest,
} from './model.js'
import css from './Transfer.module.css'
export function PreviewDetails({ preview, api }: { preview: Preview; api: TransferRequest }) {
  const [data, setData] = useState<Changes>(preview.changes),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false)
  useEffect(() => {
    setData(preview.changes)
    setError('')
  }, [preview.preview_id])
  async function page(offset: number) {
    setBusy(true)
    setError('')
    try {
      setData(
        await api({ operation: 'changes', preview_id: preview.preview_id, offset, limit: 20 }),
      )
    } catch (e) {
      setError(failure(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      <dl className={css.summary}>
        {preview.selected.map((id) => (
          <div key={id}>
            <dt>{labels[id]}</dt>
            <dd>
              {preview.summary[id]?.incoming ?? 0} 项来源记录
              {typeof preview.summary[id]?.conflicts === 'number' &&
              preview.summary[id].conflicts > 0
                ? ` · ${preview.summary[id].conflicts} 项冲突，${preview.rules[id] === 'use_import' ? '使用导入值' : '保留当前值'}`
                : ''}
              {Array.isArray(preview.summary[id]?.conflicts) &&
              preview.summary[id].conflicts.length > 0
                ? ` · ${preview.summary[id].conflicts.length} 项已有委托保持不变`
                : ''}
            </dd>
          </div>
        ))}
        <div>
          <dt>只读旧资料</dt>
          <dd>{preview.summary.archives?.incoming ?? 0} 条</dd>
        </div>
      </dl>
      {preview.blockers.length > 0 && (
        <div role="alert" className={css.feedback}>
          <strong>这些内容尚不能迁入，当前不会提交任何分类。</strong>
          <ul>
            {preview.blockers.map((b, i) => (
              <li key={i}>{b.message}</li>
            ))}
          </ul>
          <p>返回修改分类选择，或更正源文件后再预览。</p>
        </div>
      )}
      <h3>将发生的变化 · {data.total} 项</h3>
      {data.items.map((item, i) => (
        <article className={css.change} key={`${data.offset}-${i}`}>
          <strong>{item.name}</strong>
          {item.code && <small> {item.code}</small>}
          <small> · {item.kind}</small>
          {item.before && <p className={css.note}>原记录：{describe(item.before)}</p>}
          <p>{describe(item.after)}</p>
        </article>
      ))}
      {!data.total && !preview.blockers.length && (
        <p className={css.note}>没有正式记录需要更新；所选旧资料仍会保存在只读档案。</p>
      )}
      {data.total > 20 && (
        <div className={css.actions}>
          <button
            disabled={busy || data.offset === 0}
            onClick={() => void page(Math.max(0, data.offset - 20))}
          >
            上一页
          </button>
          <span>
            {data.offset + 1}–{Math.min(data.total, data.offset + data.items.length)} / {data.total}
          </span>
          <button
            disabled={busy || data.offset + data.items.length >= data.total}
            onClick={() => void page(data.offset + 20)}
          >
            下一页
          </button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {preview.warnings.length > 0 && (
        <details className={css.limits}>
          <summary>迁移范围与限制 · {preview.warnings.length} 项</summary>
          <ul>
            {preview.warnings.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
