import { useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import form from '../Form.module.css'
import business from '../Business.module.css'
import { FieldGroup } from '../shared/FieldGroup.js'
import { ApiError, errorText, request } from '../shared/api.js'
import { date, type Facts, type RiskProfile } from './types.js'

const notice = '仅供研究背景，不改变持仓、委托、提醒或交易。'
export function RiskPreference({ facts }: { facts: Facts }) {
  const [editing, setEditing] = useState(false)
  const bank = facts.risk_questionnaire
  return (
    <section aria-label="风险偏好" className={form.form}>
      <FieldGroup title="风险偏好" hint={notice}>
        <p>
          {facts.risk_profile
            ? `${facts.risk_profile.label} · ${facts.risk_profile.score}/${facts.risk_profile.max_score} 分 · ${date(facts.risk_profile.recorded_at)}`
            : '尚未填写风险偏好问卷。'}
        </p>
        <div>
          <button disabled={!bank} onClick={() => setEditing(true)}>
            {facts.risk_profile ? '重新填写问卷' : '填写风险偏好问卷'}
          </button>
        </div>
        {!bank && <p role="alert">当前后端未提供问卷，请确认产品版本后重试。</p>}
      </FieldGroup>
      {!!facts.risk_profile_history?.length && (
        <FieldGroup title="问卷历史" hint="保留每次明确确认的答案和当时结果。">
          {[...facts.risk_profile_history].reverse().map((r, i) => (
            <details key={i}>
              <summary>
                {date(r.recorded_at)} · {r.label} ·{' '}
                {r.tier === 'quick' ? '三题速测' : '八题完整问卷'}
              </summary>
              <dl>
                {r.answers.map((a) => (
                  <div key={a.qid}>
                    <dt>{bank?.full.find((q) => q.qid === a.qid)?.title || '问卷题目'}</dt>
                    <dd>{a.label}</dd>
                  </div>
                ))}
              </dl>
            </details>
          ))}
        </FieldGroup>
      )}
      {editing && bank && <RiskEditor facts={facts} close={() => setEditing(false)} />}
    </section>
  )
}

function RiskEditor({ facts, close }: { facts: Facts; close: () => void }) {
  const [tier, setTier] = useState<'quick' | 'full'>('quick')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<{ preview_id: string; after: Facts }>()
  const [busy, setBusy] = useState(false),
    [unknown, setUnknown] = useState(false),
    [error, setError] = useState('')
  const bank = facts.risk_questionnaire![tier]
  const ready = bank.every((q) => answers[q.qid] !== undefined && answers[q.qid] !== '')
  const finish = () => {
    window.dispatchEvent(new Event('huohuo-investment-changed'))
    close()
  }
  const prepare = async () => {
    setBusy(true)
    setError('')
    try {
      setPreview(
        await request('investment-command', {
          action: 'preview',
          command: 'risk_profile',
          payload: {
            tier,
            answers: bank.map((q) => ({ qid: q.qid, option: Number(answers[q.qid]) })),
          },
        }),
      )
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  const save = async () => {
    if (!preview) return
    setBusy(true)
    setError('')
    try {
      await request('investment-command', {
        action: 'commit',
        preview_id: preview.preview_id,
        request_key: preview.preview_id,
      })
      finish()
    } catch (e) {
      setError(errorText(e))
      if (e instanceof ApiError && e.status === 409) setPreview(undefined)
      else {
        setUnknown(true)
        setError('保存结果待核对，请先核对回执；不要重新填写问卷。')
      }
    } finally {
      setBusy(false)
    }
  }
  const reconcile = async () => {
    if (!preview) return
    setBusy(true)
    setError('')
    try {
      const result = await request<{ receipt?: { saved: boolean } }>('investment-command', {
        action: 'inspect-preview',
        preview_id: preview.preview_id,
      })
      if (result.receipt?.saved) finish()
      else {
        setUnknown(false)
        setError('尚无保存回执。请核对预览后明确确认，或取消。')
      }
    } catch (e) {
      setError(errorText(e))
      if (e instanceof ApiError && e.status === 409) {
        setPreview(undefined)
        setUnknown(false)
      }
    } finally {
      setBusy(false)
    }
  }
  const profile = preview?.after.risk_profile as RiskProfile | undefined
  return (
    <DetailPanel
      title="风险偏好问卷"
      close={() => {
        if (!busy) close()
      }}
    >
      <div className={form.form}>
        <p className={business.note}>{notice} 此问卷为自述偏好，不是券商适当性认证。</p>
        {error && (
          <p role="alert" className={form.error}>
            {error}
          </p>
        )}
        {profile ? (
          <>
            <FieldGroup title="保存前核对" hint="结果由固定题库计分，确认后才保存。">
              <strong>
                {profile.label} · {profile.score}/{profile.max_score} 分
              </strong>
              {profile.answers.map((a) => (
                <p key={a.qid}>
                  {bank.find((q) => q.qid === a.qid)?.title}
                  <br />
                  <strong>{a.label}</strong>
                </p>
              ))}
            </FieldGroup>
            <div className={form.actions}>
              {unknown ? (
                <button data-variant="primary" disabled={busy} onClick={() => void reconcile()}>
                  核对保存结果
                </button>
              ) : (
                <button data-variant="primary" disabled={busy} onClick={() => void save()}>
                  {busy ? '正在保存…' : '确认保存'}
                </button>
              )}
              <button
                disabled={busy || unknown}
                onClick={() => {
                  setPreview(undefined)
                  setError('')
                }}
              >
                返回修改
              </button>
              <button disabled={busy} onClick={close}>
                关闭
              </button>
            </div>
          </>
        ) : (
          <form
            className={form.form}
            onSubmit={(e) => {
              e.preventDefault()
              void prepare()
            }}
          >
            <fieldset disabled={busy} className={form.form}>
              <FieldGroup title="问卷类型">
                <label>
                  选择问卷
                  <select
                    value={tier}
                    onChange={(e) => {
                      setTier(e.target.value as typeof tier)
                      setAnswers({})
                      setError('')
                    }}
                  >
                    <option value="quick">三题速测</option>
                    <option value="full">八题完整问卷</option>
                  </select>
                </label>
              </FieldGroup>
              <FieldGroup title="你的当前情况" hint="每题选择一项；没有默认答案。">
                {bank.map((q, i) => (
                  <label key={q.qid}>
                    {i + 1}. {q.title}
                    <select
                      required
                      value={answers[q.qid] ?? ''}
                      onChange={(e) => setAnswers((old) => ({ ...old, [q.qid]: e.target.value }))}
                    >
                      <option value="" disabled>
                        请选择
                      </option>
                      {q.options.map((label, option) => (
                        <option key={option} value={String(option)}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </FieldGroup>
            </fieldset>
            <div className={form.actions}>
              <button data-variant="primary" disabled={busy || !ready}>
                {busy ? '正在核对…' : '下一步：核对结果'}
              </button>
              <button type="button" disabled={busy} onClick={close}>
                取消
              </button>
            </div>
          </form>
        )}
      </div>
    </DetailPanel>
  )
}
