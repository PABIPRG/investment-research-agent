import css from '../Form.module.css'
import { FieldGroup } from '../shared/FieldGroup.js'
import type { InvestmentDraft } from './editor-model.js'
import { SecurityPicker } from './SecurityPicker.js'
import { quantityUnit } from './types.js'
import type { EditTarget } from './types.js'
export function InvestmentFields({
  target,
  draft: d,
  change,
  disabled,
}: {
  target: EditTarget
  draft: InvestmentDraft
  change: (patch: Partial<InvestmentDraft>) => void
  disabled: boolean
}) {
  const trade = target.kind === 'trade' || target.kind === 'revision'
  return (
    <>
      <FieldGroup title="证券">
        <SecurityPicker
          value={d.security}
          onChange={(security) => change({ security })}
          locked={!!target.position || !!target.trade || target.kind === 'remove'}
          disabled={disabled}
        />
      </FieldGroup>
      {target.kind === 'revision' && (
        <fieldset>
          <legend>如何更正这笔成交</legend>
          {(['amend', 'void'] as const).map((op) => (
            <label key={op} className={css.choice}>
              <input
                type="radio"
                checked={d.revisionOp === op}
                onChange={() => change({ revisionOp: op })}
              />
              {op === 'amend' ? '修正成交内容' : '撤销这笔记录'}
            </label>
          ))}
        </fieldset>
      )}
      {target.kind !== 'watchlist' && d.revisionOp !== 'void' && (
        <FieldGroup title={trade ? '成交信息' : '持仓信息'}>
          <div className={css.grid}>
            <label>
              数量（{quantityUnit(d.security)}）
              <input
                type="number"
                required
                min={target.kind === 'holding' ? 0 : 0.000001}
                max="1000000000000"
                step="any"
                value={d.quantity}
                onChange={(e) => change({ quantity: e.target.value })}
              />
            </label>
            <label>
              {target.kind === 'holding'
                ? `成本（元/${quantityUnit(d.security)}，可留空）`
                : `成交价格（元/${quantityUnit(d.security)}）`}
              <input
                type="number"
                required={target.kind !== 'holding'}
                min="0"
                max="1000000000000"
                step="any"
                value={d.price}
                onChange={(e) => change({ price: e.target.value })}
              />
            </label>
            <label>
              {target.kind === 'holding' ? '持仓确认时间' : '实际成交时间'}
              <input
                type="datetime-local"
                required
                value={d.at}
                onChange={(e) => change({ at: e.target.value })}
              />
            </label>
            {trade && (
              <label>
                费用（元）
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={d.fees}
                  onChange={(e) => change({ fees: e.target.value })}
                />
              </label>
            )}
          </div>
        </FieldGroup>
      )}
      {trade && (
        <FieldGroup title="记录方式">
          <div className={css.grid}>
            {d.revisionOp !== 'void' && (
              <fieldset>
                <legend>成交方向</legend>
                {['buy', 'sell'].map((side) => (
                  <label key={side} className={css.choice}>
                    <input
                      type="radio"
                      checked={d.side === side}
                      onChange={() => change({ side })}
                    />
                    {side === 'buy' ? '买入' : '卖出'}
                  </label>
                ))}
              </fieldset>
            )}
            <fieldset>
              <legend>对持仓的影响</legend>
              <label className={css.choice}>
                <input
                  type="radio"
                  checked={d.affects}
                  onChange={() => change({ affects: true })}
                />
                同步更新持仓
              </label>
              <label className={css.choice}>
                <input
                  type="radio"
                  checked={!d.affects}
                  onChange={() => change({ affects: false })}
                />
                只补录成交，不调整持仓
              </label>
            </fieldset>
          </div>
        </FieldGroup>
      )}
      {target.kind !== 'trade' && (
        <label>
          {target.kind === 'watchlist' ? '关注原因' : '记录原因'}
          <textarea
            required={target.kind === 'holding'}
            maxLength={500}
            value={d.reason}
            onChange={(e) => change({ reason: e.target.value })}
            placeholder={
              target.kind === 'holding' ? '例如：根据券商账户核对当前持仓' : '补充这次记录的原因'
            }
          />
        </label>
      )}
      <small>
        {target.kind === 'watchlist'
          ? '加入自选不会创建委托或开启提醒。'
          : target.kind === 'holding'
            ? '这里保存持仓事实，不产生买卖成交。时间使用本机时区。'
            : '只记录已经发生的成交，不向券商下单。时间使用本机时区。'}
      </small>
    </>
  )
}
