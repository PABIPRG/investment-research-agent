import { useState } from 'react'
import { toleranceLabel } from './risk-adjustment-model.js'
import { date, type Facts } from './types.js'
import { RiskEditor } from './RiskQuestionnaireEditor.js'
import { RiskAdjustment } from './RiskAdjustment.js'
import { RiskPolicyView } from './RiskPolicyView.js'
import { InvestmentSection } from './InvestmentSection.js'
import ui from './Sections.module.css'
export function RiskPreference({ facts }: { facts: Facts }) {
  const [editing, setEditing] = useState(false)
  const bank = facts.risk_questionnaire,
    profile = facts.risk_profile
  return (
    <section aria-label="风险偏好" className={ui.stack}>
      <InvestmentSection
        title="你的风险偏好"
        hint="用于研究预算与建议校准，不自动交易或修改联系约定。"
        actions={
          <>
            <button
              data-variant={profile ? undefined : 'primary'}
              disabled={!bank}
              onClick={() => setEditing(true)}
            >
              {profile ? '重新填写问卷' : '填写风险偏好问卷'}
            </button>
            <RiskAdjustment facts={facts} />
          </>
        }
      >
        {profile ? (
          <dl className={ui.metrics}>
            <div>
              <dt>当前生效画像</dt>
              <dd>{profile.label}</dd>
            </div>
            <div>
              <dt>问卷得分</dt>
              <dd>
                {profile.score} / {profile.max_score}
              </dd>
            </div>
            <div>
              <dt>问卷方式</dt>
              <dd>{profile.tier === 'quick' ? '三题速测' : '八题完整问卷'}</dd>
            </div>
            <div>
              <dt>确认时间</dt>
              <dd style={{ fontSize: '1rem' }}>{date(profile.recorded_at)}</dd>
            </div>
          </dl>
        ) : (
          <p className={ui.empty}>
            填写问卷后，火火会按你确认的偏好解释研究风险。尚未填写时，不会将默认档位当作你的选择。
          </p>
        )}
        {!bank && <p role="alert">当前实例未提供问卷，请刷新后重试。</p>}
      </InvestmentSection>
      <RiskPolicyView facts={facts} />
      {!!facts.risk_profile_history?.length && (
        <details className={ui.disclosure}>
          <summary>偏好历史 · {facts.risk_profile_history.length} 次确认</summary>
          <div>
            {[...facts.risk_profile_history].reverse().map((r, i) => (
              <details key={i} className={ui.record}>
                <summary>
                  {date(r.recorded_at)} · {r.label} ·{' '}
                  {r.method === 'manual_adjust'
                    ? '手动调整'
                    : r.tier === 'quick'
                      ? '三题速测'
                      : '八题完整问卷'}
                </summary>
                {r.statement && <p>经核对的描述：{r.statement}</p>}
                <dl className={ui.facts}>
                  {r.answers.map((a) => (
                    <div key={a.qid}>
                      <dt>{bank?.full.find((q) => q.qid === a.qid)?.title || '问卷题目'}</dt>
                      <dd>{a.label}</dd>
                    </div>
                  ))}
                </dl>
                {r.manual_adjust && (
                  <p>
                    接受波动的意愿：{toleranceLabel(r.manual_adjust.risk_tolerance)}；资金期限{' '}
                    {r.manual_adjust.horizon_years} 年；原问卷分数保留。
                  </p>
                )}
              </details>
            ))}
          </div>
        </details>
      )}
      {editing && bank && <RiskEditor facts={facts} close={() => setEditing(false)} />}
    </section>
  )
}
