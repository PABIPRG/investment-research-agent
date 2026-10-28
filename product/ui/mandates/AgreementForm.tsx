import { Select } from '../shared/Select.js'
import { FieldGroup } from '../shared/FieldGroup.js'
import form from '../Form.module.css'
import { ContactRuleEditor } from './ContactRuleEditor.js'
import { channelLabels } from '../notifications/model.js'
import css from '../Query.module.css'
import type { MandateController } from './useMandates.js'
export function AgreementForm({ model }: { model: MandateController }) {
  const {
    busy,
    command,
    contactChannels,
    setContactChannels,
    goal,
    setGoal,
    note,
    setNote,
    reminder,
    setReminder,
    reminderTime,
    setReminderTime,
    setEditing,
  } = model
  return (
    <form
      className={css.editForm}
      onSubmit={(e) => {
        e.preventDefault()
        void command('revise')
      }}
    >
      <FieldGroup title="联系渠道">
        <fieldset disabled={busy}>
          {Object.entries(channelLabels).map(([c, label]) => (
            <label className={css.checkLabel} key={c}>
              <input
                type="checkbox"
                checked={contactChannels.includes(c)}
                onChange={(e) =>
                  setContactChannels((old) =>
                    e.target.checked ? [...old, c] : old.filter((x) => x !== c),
                  )
                }
              />
              {label}
            </label>
          ))}
          <p className={css.note}>
            外部渠道需先在提醒方式中保存并启用。保存约定后，本委托可通过所选渠道发送研究摘要；在途请求无法撤回。
          </p>
        </fieldset>
      </FieldGroup>
      <FieldGroup title="研究内容">
        <label>
          研究目标
          <textarea
            required
            maxLength={4000}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
        </label>
        <label>
          联系与研究约定
          <textarea
            required
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
      </FieldGroup>
      <FieldGroup title="资料与联系规则">
        <label>
          研究资料
          <Select value={model.operation} onChange={(e) => model.setOperation(e.target.value)}>
            {!['market_quote', 'market_technical', 'news', 'market_brief'].includes(
              model.current?.revision.scope.operation || '',
            ) && <option value={model.current?.revision.scope.operation}>保留当前研究范围</option>}
            <option value="market_quote">行情与量价指标</option>
            <option value="market_technical">日线技术指标</option>
            <option value="news">相关新闻</option>
            <option value="market_brief">盘前 / 盘后简报</option>
          </Select>
        </label>
        {model.operation === 'market_brief' && (
          <label>
            简报时段
            <Select
              value={model.briefPeriod}
              onChange={(e) => model.setBriefPeriod(e.target.value)}
            >
              <option value="pre">盘前</option>
              <option value="post">盘后</option>
            </Select>
          </label>
        )}
        <ContactRuleEditor
          value={model.contactRule}
          change={model.setContactRule}
          operation={model.operation}
        />
      </FieldGroup>
      <p className={css.note}>保存后产生新版本，旧研究资格将撤销。研究对象保持不变。</p>
      <div className={form.actions}>
        <button className={css.button} data-variant="primary" disabled={busy}>
          确认保存
        </button>
        <button type="button" className={css.textButton} onClick={() => setEditing(false)}>
          取消修改
        </button>
      </div>
    </form>
  )
}
