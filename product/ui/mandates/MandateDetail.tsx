import { useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import form from '../Form.module.css'
import { InvestmentContext } from '../InvestmentContext.js'
import css from '../Query.module.css'
import { mandateName } from '../business-model.js'
import { arrivalStatus, canRetryBaseline } from '../shell/arrival-model.js'
import { semanticCondition } from './ContactRuleEditor.js'
import { AgreementForm } from './AgreementForm.js'
import { MandateDecisions } from './MandateDecisions.js'
import { ResearchHistory } from './ResearchHistory.js'
import { TriggerSummary } from './TriggerFilter.js'
import { MandateEvidence } from './MandateEvidence.js'
import { statuses, sourceReason } from './model.js'
import type { MandateController } from './useMandates.js'
export function MandateDetail({ model }: { model: MandateController }) {
  const [confirm, setConfirm] = useState<'pause' | 'end'>()
  const {
    current,
    heading,
    busy,
    loading,
    error,
    editing,
    setEditing,
    setContactChannels,
    setGoal,
    setNote,
    setReminder,
    setReminderTime,
    command,
    feedback,
  } = model
  if (!current) return null
  const state = arrivalStatus(current)
  const edit = () => {
    setContactChannels(current.revision.contact_policy?.channels || ['app'])
    setGoal(current.revision.goal)
    setNote(current.revision.basis.contact_note || '')
    setReminder(!!current.revision.contact_policy?.reminder_time)
    setReminderTime(current.revision.contact_policy?.reminder_time || '09:00')
    model.setOperation(current.revision.scope.operation)
    model.setBriefPeriod(current.revision.scope.period === 'pre' ? 'pre' : 'post')
    model.setContactRule(
      current.revision.basis.contact_rule ||
        (current.revision.contact_policy?.reminder_time
          ? {
              mode: 'due_reminder',
              time: current.revision.contact_policy.reminder_time,
              trading_days_only: false,
            }
          : { mode: 'condition', condition: semanticCondition }),
    )
    setEditing(true)
  }
  const disabled = busy || loading || !!error || current.mandate.status === 'ended'
  return (
    <DetailPanel
      title={`${mandateName(current)} · 委托详情`}
      close={() => {
        if (!busy) {
          model.setSelected(undefined)
          sessionStorage.removeItem('huohuo-return')
        }
      }}
    >
      <section className={css.detail}>
        <h3 ref={heading} tabIndex={-1} className={css.question}>
          {current.revision.goal}
        </h3>
        <p className={css.note}>
          {statuses[current.mandate.status]} · 范围 v{current.mandate.current_revision} ·{' '}
          {current.revision.scope.entity_id.split(':').at(-1)}
        </p>
        <section className={css.section}>
          <h3>当前情况</h3>
          <p className={css.summary}>
            {current.mandate.status === 'paused'
              ? '已暂停，恢复前不会开始新的跟进'
              : current.mandate.status === 'ended'
                ? '这项委托已结束'
                : state.title}
          </p>
          <p>{state.detail}</p>
          <p className={css.note}>{current.monitoring.detail}</p>
          <TriggerSummary item={current} />
          {current.execution_mode === 'program_price' && (
            <p className={css.note}>价格条件由程序执行，不额外调用研究模型。</p>
          )}
          {current.source_check && current.source_check.status !== 'ok' && (
            <p className={css.note}>最近资料检查：{sourceReason(current.source_check.detail)}</p>
          )}
          {canRetryBaseline(current) && (
            <button disabled={disabled} onClick={() => void command('retry_baseline')}>
              重新建立研究基准
            </button>
          )}
        </section>
        <section className={css.section}>
          <h3>联系与研究约定</h3>
          <p>{current.contact_rule_description}</p>
          <p>{current.revision.basis.contact_note || '尚无补充约定'}</p>
          {editing ? (
            <AgreementForm model={model} />
          ) : (
            <button data-variant="primary" disabled={disabled} onClick={edit}>
              修改约定
            </button>
          )}
          {feedback && <p role="status">{feedback}</p>}
        </section>
        <details className={css.section} open={!!model.returnExecution}>
          <summary>研究记录 · {current.executions.length} 次</summary>
          <ResearchHistory current={current} returnExecution={model.returnExecution} />
        </details>
        <details className={css.section} open={!!model.returnDecision}>
          <summary>复核与提醒记录 · {current.decisions?.length || 0} 条</summary>
          <MandateDecisions current={current} returnDecision={model.returnDecision} />
        </details>
        <details className={css.section}>
          <summary>全部参考资料 · {current.evidence.length} 条</summary>
          <MandateEvidence current={current} />
        </details>
        <details className={css.section}>
          <summary>研究时参考的持仓与自选</summary>
          <InvestmentContext current={current} updated={() => model.setRefresh((n) => n + 1)} />
        </details>
        <details className={css.section}>
          <summary>管理委托</summary>
          <p className={css.note}>
            暂停可以恢复；结束后不能恢复这项委托。已交给渠道的在途消息无法撤回。
          </p>
          <div className={css.actions}>
            {current.mandate.status === 'paused' ? (
              <button disabled={disabled} onClick={() => void command('resume')}>
                恢复委托
              </button>
            ) : (
              <button disabled={disabled} onClick={() => setConfirm('pause')}>
                暂停委托
              </button>
            )}
            <button data-variant="danger" disabled={disabled} onClick={() => setConfirm('end')}>
              结束委托
            </button>
          </div>
          {confirm && (
            <div className={form.error}>
              <strong>{confirm === 'end' ? '确认结束这项委托？' : '确认暂停这项委托？'}</strong>
              <p>
                {confirm === 'end'
                  ? '结束后不可恢复，已保存记录和证据仍保留。'
                  : '暂停后阻止新的研究与发送资格，已有在途消息无法撤回。'}
              </p>
              <div className={css.actions}>
                <button
                  data-variant={confirm === 'end' ? 'danger' : 'primary'}
                  disabled={busy}
                  onClick={() => {
                    void command(confirm)
                    setConfirm(undefined)
                  }}
                >
                  确认{confirm === 'end' ? '结束' : '暂停'}
                </button>
                <button disabled={busy} onClick={() => setConfirm(undefined)}>
                  取消
                </button>
              </div>
            </div>
          )}
        </details>
      </section>
    </DetailPanel>
  )
}
