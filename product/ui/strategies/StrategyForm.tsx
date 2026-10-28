import { Select } from '../shared/Select.js'
import { FieldGroup } from '../shared/FieldGroup.js'
import { useState } from 'react'
import { SecurityPicker } from '../investment/SecurityPicker.js'
import type { Security } from '../investment/types.js'
import { defaults, paramLabels, ruleLabels } from './model.js'
import form from '../Form.module.css'
export function StrategyForm({ submit, busy }: { submit: (payload: any) => void; busy: boolean }) {
  const [security, setSecurity] = useState<Security>(),
    [kind, setKind] = useState('ma_cross'),
    [params, setParams] = useState(defaults.ma_cross)
  return (
    <form
      className={form.form}
      onSubmit={(e) => {
        e.preventDefault()
        const data = new FormData(e.currentTarget)
        if (security)
          submit({
            name: data.get('name'),
            kind,
            params,
            securities: [{ code: security.code, name: security.name }],
            rationale: data.get('rationale'),
            direction: data.get('direction'),
          })
      }}
    >
      <FieldGroup title="研究对象">
        <label>
          策略名称
          <input
            name="name"
            required
            maxLength={100}
            placeholder="例如：贵州茅台均线观察"
            disabled={busy}
          />
        </label>
        <SecurityPicker value={security} onChange={setSecurity} disabled={busy} />
      </FieldGroup>
      <FieldGroup title="验证设定">
        <div className={form.grid}>
          <label>
            验证规则
            <Select
              value={kind}
              disabled={busy}
              onChange={(e) => {
                setKind(e.target.value)
                setParams(defaults[e.target.value])
              }}
            >
              {Object.entries(ruleLabels).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </Select>
          </label>
          <label>
            研究方向
            <Select name="direction" disabled={busy}>
              <option>利好</option>
              <option>利空</option>
              <option>其他</option>
            </Select>
          </label>
        </div>
        <div className={form.grid}>
          {Object.keys(params).map((key) => (
            <label key={key}>
              {paramLabels[key]}
              <input
                type="number"
                step="any"
                required
                value={params[key]}
                disabled={busy}
                onChange={(e) => setParams({ ...params, [key]: Number(e.target.value) })}
              />
            </label>
          ))}
        </div>
        <label>
          研究假设
          <textarea
            name="rationale"
            required
            maxLength={1000}
            disabled={busy}
            placeholder="希望用什么规则验证什么判断？"
          />
        </label>
        <p className={form.hint}>保存为待验证候选。利空假设也只验证做多反弹，不模拟做空。</p>
      </FieldGroup>
      <div className={form.actions}>
        <button data-variant="primary" disabled={busy || !security} type="submit">
          {busy ? '正在准备预览…' : '预览策略'}
        </button>
      </div>
    </form>
  )
}
