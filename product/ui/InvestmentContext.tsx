import { useState } from 'react'
import { time } from './model.js'
import css from './InvestmentContext.module.css'
export function InvestmentContext({ current, updated }: { current: any; updated: () => void }) {
  const [collection, setCollection] = useState('holdings'),
    [mode, setMode] = useState('fixed'),
    [preview, setPreview] = useState<any>(),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false)
  const request = async (body: unknown) => {
    const r = await fetch('api/huohuo/investment-command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const x = await r.json()
    if (!r.ok) throw new Error(x.detail || '读取失败')
    return x
  }
  const inspect = async () => {
    setBusy(true)
    setError('')
    try {
      setPreview(await request({ action: 'collection', collection, version: null }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const bind = async () => {
    setBusy(true)
    setError('')
    try {
      await request({
        action: 'bind-collection',
        mandate_id: current.mandate.mandate_id,
        collection,
        mode,
        expected_revision: current.mandate.current_revision,
        expected_generation: current.generation,
        expected_fact_version: preview.fact_version,
        request_key: `collection:${current.mandate.mandate_id}:${current.mandate.current_revision}:${preview.fact_version}:${collection}:${mode}`,
      })
      setPreview(undefined)
      updated()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className={`${css.editor} ${css.context}`}>
      <h3>研究参考哪些投资记录</h3>
      <p className={css.note}>
        可以让研究参考你的持仓或自选。研究对象仍限于这项委托，不会自动研究其他证券。
      </p>
      {current.investment_collection && (
        <p>
          已关联{current.investment_collection.collection === 'holdings' ? '持仓' : '自选'} ·{' '}
          {current.investment_collection.mode === 'fixed' ? '保留关联时的记录' : '随投资记录更新'} ·
          关联时记录版本 {current.investment_collection.bound_version}
        </p>
      )}
      <div className={css.fields}>
        <fieldset>
          <legend>参考内容</legend>
          {[
            ['holdings', '我的持仓'],
            ['watchlist', '我的自选'],
          ].map(([v, l]) => (
            <label key={v}>
              <input
                type="radio"
                checked={collection === v}
                onChange={() => {
                  setCollection(v)
                  setPreview(undefined)
                }}
              />
              {l}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>更新方式</legend>
          {[
            ['fixed', '始终参考关联时的记录'],
            ['dynamic', '每次研究参考最新记录'],
          ].map(([v, l]) => (
            <label key={v}>
              <input
                type="radio"
                checked={mode === v}
                onChange={() => {
                  setMode(v)
                  setPreview(undefined)
                }}
              />
              {l}
            </label>
          ))}
        </fieldset>
      </div>
      <button disabled={busy || current.mandate.status === 'ended'} onClick={() => void inspect()}>
        预览参考内容
      </button>
      {preview && (
        <div>
          <p>
            事实版本 {preview.fact_version} ·{' '}
            {preview.status === 'not_recorded'
              ? '尚未录入'
              : preview.members.length
                ? preview.members.map((x: any) => x.name).join('、')
                : '当前没有记录'}
          </p>
          <p>
            确认后，新研究使用此约定；按旧约定启动的研究不能再作为当前结果。已暂停的委托仍保持暂停。
          </p>
          <button disabled={busy || preview.status === 'not_recorded'} onClick={() => void bind()}>
            确认关联
          </button>
          <button disabled={busy} onClick={() => setPreview(undefined)}>
            取消
          </button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {current.fact_snapshots?.map((x: any) => (
        <p key={x.execution_id} className={css.note}>
          研究时间{' '}
          {time(
            current.executions?.find(
              (e: { execution_id: string }) => e.execution_id === x.execution_id,
            )?.created_at,
          )}{' '}
          · 参考记录版本 {x.version} ·{' '}
          {x.mode === 'fixed'
            ? '保留关联时的记录'
            : x.mode === 'dynamic'
              ? '动态快照'
              : '执行时快照'}
        </p>
      ))}
    </section>
  )
}
