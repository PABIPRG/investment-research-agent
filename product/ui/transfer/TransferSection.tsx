import controls from '../shared/Controls.module.css'
import { Select } from '../shared/Select.js'
import { useRef, useState } from 'react'
import { ArchiveView } from './ArchiveView.js'
import { PreviewDetails } from './PreviewDetails.js'
import { effects, type Rule, type TransferRequest } from './model.js'
import { useTransfer } from './useTransfer.js'
import form from '../Form.module.css'
import css from './Transfer.module.css'
export function TransferSection({ api: providedApi }: { api?: TransferRequest }) {
  const {
    api,
    uploads,
    upload,
    selected,
    setSelected,
    rules,
    setRules,
    preview,
    receipt,
    busy,
    error,
    unknown,
    locked,
    check,
    choose,
    file,
    prepare,
    commit,
    back,
    remove,
  } = useTransfer(providedApi)
  const [showArchive, setShowArchive] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  return (
    <section className={`${css.root} ${controls.controls}`} aria-label="旧数据导入">
      <header className={css.header}>
        <div>
          <h2>旧数据导入</h2>
          <p>迁入旧产品记录，先核对，再确认保存。</p>
        </div>
        <button onClick={() => setShowArchive((v) => !v)}>
          {showArchive ? '返回导入' : '旧资料档案'}
        </button>
      </header>
      {showArchive ? (
        <ArchiveView api={api} />
      ) : (
        <>
          {error && (
            <p className={css.feedback} role="alert">
              {error}
            </p>
          )}
          {busy && <p role="status">正在处理，请稍候…</p>}
          {unknown && (
            <div className={css.feedback}>
              <strong>需要核对这次导入的状态</strong>
              <p>连接恢复后查询同一份回执，不会自动再次提交。</p>
              <button disabled={busy} onClick={() => void check()}>
                核对导入回执
              </button>
            </div>
          )}
          {receipt ? (
            <div className={css.receipt} role="status">
              <h3>导入已保存</h3>
              <p>
                投资事实
                {receipt.result.facts.changed
                  ? `已更新到版本 ${receipt.result.facts.version}`
                  : '保持不变'}
                ；新增策略 {receipt.result.strategies} 项、暂停委托 {receipt.result.mandates}{' '}
                项、只读档案 {receipt.result.archives_added} 条。
              </p>
              <p className={css.note}>
                {new Date(receipt.imported_at).toLocaleString()} · 正式记录和迁移回执已一起保存。
              </p>
              <div className={css.actions}>
                <button onClick={() => setShowArchive(true)}>查看旧资料档案</button>
                <button onClick={() => void back()}>完成，返回文件选择</button>
              </div>
            </div>
          ) : preview ? (
            <>
              <div className={form.steps}>
                <span>1 文件与分类</span>
                <strong>2 核对并确认</strong>
              </div>
              <PreviewDetails preview={preview} api={api} />
              {preview.status !== 'pending' && (
                <p role="status">
                  {preview.status === 'expired'
                    ? '预览已过期，请返回重新预览。'
                    : preview.status === 'stale'
                      ? '正式记录已发生变化。请取消旧预览，重新核对本次导入。'
                      : '这份预览已取消或已失效。'}
                </p>
              )}
              <p className={css.note}>
                确认后一次写入全部所选分类；不会恢复旧运行任务或对外发送消息。
              </p>
              <div className={css.actions}>
                <button
                  disabled={busy || unknown || !preview.can_commit}
                  data-variant="primary"
                  onClick={() => void commit()}
                >
                  确认导入所选数据
                </button>
                <button disabled={busy || unknown} onClick={() => void back()}>
                  取消预览，返回选择
                </button>
                <button disabled={busy} onClick={() => void check()}>
                  核对回执
                </button>
              </div>
            </>
          ) : (
            <>
              <div className={css.file}>
                <div className={css.fileAction}>
                  <button
                    disabled={locked}
                    data-variant="primary"
                    onClick={() => fileInput.current?.click()}
                  >
                    {busy ? '正在读取文件…' : '选择 JSON 文件'}
                  </button>
                  <span className={css.note}>最多 20 MB</span>
                </div>
                <p className={css.note}>上传后可选择要迁入的内容，确认前不会改变现有记录。</p>
                <input
                  ref={fileInput}
                  hidden
                  aria-label="选择旧产品数据文件"
                  disabled={locked}
                  type="file"
                  accept=".json,application/json"
                  onChange={(e) => {
                    void file(e.target.files?.[0])
                    e.target.value = ''
                  }}
                />
              </div>
              <details className={css.limits}>
                <summary>支持的文件与导入范围</summary>
                <p>
                  使用旧产品导出的 JSON 文件，支持 trading-core schema 1–4 和产品数据包 format 1。
                </p>
                <p>
                  持仓、自选、策略和研究资料可分别选择。策略需重新验证，持续委托迁入后保持暂停。
                </p>
                <p>不恢复模型密钥、旧通知授权或运行任务；附件仅保留缺失清单。</p>
              </details>
              {uploads.length > 0 && (
                <div className={css.uploads}>
                  <h3>已上传的候选文件</h3>
                  {uploads.map((item) => (
                    <div key={item.upload_id}>
                      <button
                        aria-pressed={upload?.upload_id === item.upload_id}
                        disabled={locked}
                        onClick={() => choose(item)}
                      >
                        {item.filename}
                      </button>
                      <button disabled={locked} onClick={() => void remove(item.upload_id)}>
                        移除候选
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {upload && (
                <form
                  className={form.form}
                  onSubmit={(e) => {
                    e.preventDefault()
                    void prepare()
                  }}
                >
                  <fieldset disabled={locked}>
                    <legend>选择要迁入的数据</legend>
                    {upload.categories.map((item) => (
                      <div className={css.category} key={item.id}>
                        <label className={form.choice}>
                          <input
                            type="checkbox"
                            checked={selected.includes(item.id)}
                            onChange={(e) =>
                              setSelected((v) =>
                                e.target.checked ? [...v, item.id] : v.filter((x) => x !== item.id),
                              )
                            }
                          />
                          {item.label}
                        </label>
                        <p className={css.note}>{effects[item.id]}</p>
                        {selected.includes(item.id) &&
                          ['holdings', 'strategies'].includes(item.id) && (
                            <label>
                              出现冲突时
                              <Select
                                value={rules[item.id] ?? 'keep_local'}
                                onChange={(e) =>
                                  setRules((v) => ({ ...v, [item.id]: e.target.value as Rule }))
                                }
                              >
                                <option value="keep_local">保留当前记录</option>
                                <option value="use_import">使用导入值（在下一步核对）</option>
                              </Select>
                            </label>
                          )}
                      </div>
                    ))}
                  </fieldset>
                  {upload.warnings.length > 0 && (
                    <details className={css.limits}>
                      <summary>文件范围与限制 · {upload.warnings.length} 项</summary>
                      <ul>
                        {upload.warnings.map((x, i) => (
                          <li key={i}>{x}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  <div className={css.actions}>
                    <button
                      type="submit"
                      data-variant="primary"
                      disabled={locked || !selected.length}
                    >
                      预览导入影响
                    </button>
                    <span className={css.note}>当前还未修改正式记录</span>
                  </div>
                </form>
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
