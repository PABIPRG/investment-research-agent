import { mandateName } from '../business-model.js'
import business from '../Business.module.css'
import { channelLabels } from '../notifications/model.js'
import { sourceReason, statuses } from './model.js'
import type { MandateController } from './useMandates.js'
export function MandateTable({ model }: { model: MandateController }) {
  const { items, filter, loading, error, setSelected } = model
  const rows = items.filter((x) => filter === 'all' || x.mandate.status === filter)
  return (
    <div className={business.tableWrap}>
      <table className={business.table}>
        <thead>
          <tr>
            {['对象 / 目标', '当前状态', '已完成 / 缺口', '下一次触发', '联系约定', '操作'].map(
              (label) => (
                <th key={label}>{label}</th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {!loading && !error && !rows.length && (
            <tr>
              <td colSpan={6} className={business.empty}>
                {items.length ? '当前筛选没有委托，请切换“全部”。' : '尚无已确认的持续研究委托。'}
              </td>
            </tr>
          )}
          {rows.map((x) => (
            <tr key={x.mandate.mandate_id}>
              <td>
                <strong>{mandateName(x)}</strong>
                <small>{x.revision.goal}</small>
                <small>{x.revision.scope.entity_id.split(':').at(-1)}</small>
              </td>
              <td>
                {statuses[x.mandate.status] || '状态待核对'}
                <small>
                  范围 v{x.mandate.current_revision} ·{' '}
                  {statuses[x.executions[0]?.status] || '等待初次调度'}
                </small>
              </td>
              <td>
                {x.execution_mode === 'program_price'
                  ? '价格条件由程序核对'
                  : x.requires_comparison_baseline === false
                    ? '无需比较基准'
                    : x.baseline
                      ? '已留存研究基准'
                      : '尚无有效基准'}
                <small>
                  {x.source_check?.status && x.source_check.status !== 'ok'
                    ? sourceReason(x.source_check.detail)
                    : x.decisions?.[0]?.condition_result === 'unknown'
                      ? '资料不足，尚不能判断'
                      : `${x.evidence.length} 条留存证据`}
                </small>
              </td>
              <td>
                {x.mandate.status === 'paused'
                  ? '恢复委托后再跟进'
                  : x.mandate.status === 'ended'
                    ? '已结束'
                    : x.monitoring?.enabled
                      ? x.monitoring.detail.split('；')[0]
                      : '持续资料发现尚未接入'}
              </td>
              <td>
                {x.revision.basis.contact_note || '未补充约定'}
                <small>
                  {(x.revision.contact_policy?.channels || ['app'])
                    .map((c) => channelLabels[c] || c)
                    .join('、')}
                </small>
              </td>
              <td>
                <button onClick={() => setSelected(x.mandate.mandate_id)}>详情</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
