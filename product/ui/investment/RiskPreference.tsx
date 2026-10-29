import { useState } from 'react'
import form from '../Form.module.css'
import { FieldGroup } from '../shared/FieldGroup.js'
import { date, type Facts } from './types.js'

import { RiskEditor } from './RiskQuestionnaireEditor.js'
import { RiskAdjustment } from './RiskAdjustment.js'
import { RiskPolicyView } from './RiskPolicyView.js'
const notice = '有效画像用于风险预算、研究建议护栏和个性化匹配；不自动交易或更改联系授权。'
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
      <RiskAdjustment facts={facts} />
      <RiskPolicyView facts={facts} />
      {!!facts.risk_profile_history?.length && (
        <FieldGroup title="问卷历史" hint="保留每次明确确认的答案和当时结果。">
          {[...facts.risk_profile_history].reverse().map((r, i) => (
            <details key={i}>
              <summary>
                {date(r.recorded_at)} · {r.label} ·{' '}
                {r.method === 'manual_adjust'
                  ? '手动调整'
                  : r.tier === 'quick'
                    ? '三题速测'
                    : '八题完整问卷'}
              </summary>
              <dl>
                {r.statement && <p>经核对的原始描述：{r.statement}</p>}
                {r.answers.map((a) => (
                  <div key={a.qid}>
                    <dt>{bank?.full.find((q) => q.qid === a.qid)?.title || '问卷题目'}</dt>
                    <dd>{a.label}</dd>
                  </div>
                ))}
                {r.manual_adjust && (
                  <p>
                    手动调整：承受度 {r.manual_adjust.risk_tolerance}，期限{' '}
                    {r.manual_adjust.horizon_years} 年；原问卷分数 {r.score}/{r.max_score}。
                  </p>
                )}
              </dl>
            </details>
          ))}
        </FieldGroup>
      )}
      {editing && bank && <RiskEditor facts={facts} close={() => setEditing(false)} />}
    </section>
  )
}
