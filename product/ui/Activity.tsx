import page from './shared/Page.module.css'
import css from './Business.module.css'
export { ActivityDashboard as ActivityPage } from './activity/ActivityDashboard.js'
export function PlannedPage({ kind }: { kind: 'framework' | 'evolution' }) {
  const framework = kind === 'framework'
  const headers = framework
    ? ['内容', '当前生效表述', '依据', '版本 / 日期', '操作']
    : ['候选改动', '对照与范围', '验证结果 / 限制', '状态', '操作']
  return (
    <main className={`${page.surface} ${css.page}`}>
      <header className={`${page.header} ${css.header}`}>
        <div>
          <h1>{framework ? '我的框架' : '验证与演进'}</h1>
          <p className={css.note}>{framework ? '明确偏好、判断与约定' : '候选与生效分开'}</p>
        </div>
      </header>
      <div className={css.tableWrap}>
        <table className={css.table}>
          <thead>
            <tr>
              {headers.map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={5} className={css.empty}>
                {framework
                  ? '框架记录尚未接入，暂不能读取或修改已确认的研究方法。'
                  : '验证记录尚未接入，暂不能查看对照、采用候选或回查修订。'}
                <small>此处没有可用数据，不代表你没有框架或验证记录。</small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className={css.note}>
        {framework
          ? '推测兴趣不写入明确偏好；候选调整在验证与演进中单独确认。'
          : '未经验证与确认的候选不作为已生效规则。'}
      </p>
    </main>
  )
}
