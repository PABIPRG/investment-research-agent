import { useEffect, useState } from 'react'
import css from './Query.module.css'
import styles from './Notifications.module.css'

export const channelLabels: Record<string,string> = {app:'应用内',wecom:'企业微信',serverchan:'Server 酱',email:'邮件'}
const fields: Record<string,Record<string,string>> = {wecom:{key:'机器人密钥'},serverchan:{sendkey:'SendKey'},email:{host:'SMTP 主机',port:'SMTP 端口',username:'SMTP 用户名',password:'SMTP 密码',sender:'发件邮箱',destination:'收件邮箱'}}
const secretFields=['key','sendkey','password']
type Config = { revision: number; enabled: boolean; channels: string[]; timezone: string; quiet_hours: { start: string; end: string } | null; external_status: string; external: Record<string,{configured:boolean;secret_saved:Record<string,boolean>;[key:string]:any}> }
export const deliveryLabels: Record<string,string> = { queued:'等待投递',deferred:'静默延期',retry:'等待安全重试',in_flight:'请求在途',accepted:'渠道已受理，送达未确认',delivered:'已到达应用内',unknown:'结果未知，等待对账',failed:'投递失败',cancelled:'已阻止发送' }
export function decisionText(detail: string, reason: string) {
  const readable = (detail || '').replace(/^notable_change=(?:met|unmet|unknown)\s*/, '').replace(/^（(.*)）$/, '$1')
  return readable || ({condition_met:'变化满足联系约定',no_material_change:'没有值得联系的新变化',condition_unknown:'资料不足，暂不能判断',research_failed:'研究执行失败',due_reminder:'按约到期提醒',quiet_hours:'处于静默时段'} as Record<string,string>)[reason] || '请回访委托核对判断依据'
}
async function api(path: string, body?: unknown) {
  const response=await fetch(`api/huohuo/${path}`,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store'})
  const data=await response.json();if(!response.ok)throw new Error(response.status===403?'无权访问，请重新连接。':data.detail||'读取失败，请重试。');return data
}
export function NotificationsPage({ visit }: { visit: (mandate: string, decision: string) => void }) {
  const [config,setConfig]=useState<Config>(),[rows,setRows]=useState<any[]>([]),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const [channels,setChannels]=useState<string[]>(['app']),[external,setExternal]=useState<Record<string,Record<string,any>>>({})
  const [enabled,setEnabled]=useState(false),[quiet,setQuiet]=useState(false),[start,setStart]=useState('22:00'),[end,setEnd]=useState('08:00'),[revision,setRevision]=useState(0)
  useEffect(()=>{let active=true;setLoading(true);setError('');Promise.all([api('notification-config'),api('notifications')]).then(([cfg,data])=>{if(!active)return;setConfig(cfg);setChannels(cfg.channels);setExternal(Object.fromEntries(Object.entries(cfg.external).map(([c,v]:[string,any])=>[c,Object.fromEntries(Object.keys(fields[c]).map(k=>[k,secretFields.includes(k)?'':v[k]??(k==='port'?587:'')]))])));setEnabled(cfg.enabled);setQuiet(!!cfg.quiet_hours);setStart(cfg.quiet_hours?.start||'22:00');setEnd(cfg.quiet_hours?.end||'08:00');setRows(data.items);setLoading(false)}).catch(e=>{if(active){setError(e.message);setLoading(false);if(e.message.includes('无权')){setConfig(undefined);setRows([])}}});return()=>{active=false}},[revision])
  const blocked=!!error&&/已变化|连接中断|无权|读取失败|后台暂时不可用/.test(error)
  const save=async()=>{
    if(!config||!confirm(enabled?'保存当前渠道与静默设置？已明确允许这些渠道的委托，后续可能发送研究摘要。仅配置渠道不会扩大委托授权。':'关闭提醒后，尚未开始的发送会被阻止。在途请求无法撤回。确认保存？'))return
    setBusy(true);setNotice('')
    try{const cfg=await api('notification-config',{expected_revision:config.revision,enabled,channels,external,timezone:config.timezone,quiet_hours:quiet?{start,end}:null});setConfig(cfg);setExternal(old=>Object.fromEntries(Object.entries(old).map(([c,v])=>[c,Object.fromEntries(Object.entries(v).filter(([k])=>!secretFields.includes(k)&&k!=='clear'))])));setError('');setNotice('已保存。新发送会使用当前配置重新核验资格。')}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  return <main className={css.page}><header className={css.header}><div><p className={css.eyebrow}>火火 · 联系偏好</p><h1>消推配置</h1><p className={css.note}>只有明确委托中的重要变化才产生联系决定。配置不会替你创建新委托。</p></div><button className={css.button} disabled={loading||busy} onClick={()=>setRevision(x=>x+1)}>{loading?'读取中…':'刷新配置'}</button></header>
    {loading&&<p className={css.note} role="status">{config?'正在刷新，保留上次内容…':'正在读取联系偏好…'}</p>}
    {error&&<p className={css.error} role="alert">{error} {blocked&&config?'当前显示可能已过期，请刷新后再保存。':'请修正后重新保存，已填写内容仍保留。'}</p>}
    <section className={css.detail}>
      <h2>提醒与静默</h2>{config&&<form className={`${css.editForm} ${styles.form}`} onSubmit={e=>{e.preventDefault();void save()}}>
        <label className={css.checkLabel}><input type="checkbox" checked={enabled} disabled={busy||loading||blocked} onChange={e=>setEnabled(e.target.checked)}/>启用提醒</label>
        <p className={css.note}>应用内提醒保留委托、联系决定与证据回访。已到达不等于已读。</p>
        <label className={css.checkLabel}><input type="checkbox" checked={quiet} disabled={busy||loading||blocked} onChange={e=>setQuiet(e.target.checked)}/>设置每日静默时段</label>
        {quiet&&<div className={css.actions}><label>开始时间<input type="time" required value={start} disabled={busy} onChange={e=>setStart(e.target.value)}/></label><label>结束时间<input type="time" required value={end} disabled={busy} onChange={e=>setEnd(e.target.value)}/></label></div>}
        <p className={css.note}>时区：{config.timezone}。跨午夜时段有效；开始与结束相同表示全天静默。静默结束只复核发送资格，不重新做投资判断。</p>
        <h3>通知渠道</h3><p className={css.note}>配置只保存到本实例。还需在委托的“修改约定”中明确选择外部渠道；不会自动发送测试消息。</p>
        {Object.entries(channelLabels).map(([channel,label])=><section className={css.section} key={channel}>
          <label className={css.checkLabel}><input type="checkbox" checked={channels.includes(channel)} disabled={busy||loading||blocked} onChange={e=>setChannels(old=>e.target.checked?[...old,channel]:old.filter(x=>x!==channel))}/>{label}</label>
          {channel!=='app'&&<><p className={css.note}>{external[channel]?.clear?'保存后将清除本渠道配置':config.external[channel]?.configured?'配置已保存，未验证真实送达':'尚未配置完整'}</p>
          <details><summary>编辑{label}配置</summary><div className={styles.fields}>
            {Object.entries(fields[channel]).map(([key,label])=><label key={key}>{label}<input type={secretFields.includes(key)?'password':key==='port'?'number':'text'} autoComplete="off" min={key==='port'?1:undefined} max={key==='port'?65535:undefined} maxLength={1000} disabled={busy||loading||blocked||external[channel]?.clear} value={external[channel]?.[key]??''} placeholder={secretFields.includes(key)&&config.external[channel]?.secret_saved?.[key]?'已保存，留空保持不变':undefined} onChange={e=>setExternal(old=>({...old,[channel]:{...old[channel],[key]:key==='port'?Number(e.target.value):e.target.value}}))}/></label>)}
            <label className={css.checkLabel}><input type="checkbox" disabled={busy||loading||blocked} checked={!!external[channel]?.clear} onChange={e=>{setExternal(old=>({...old,[channel]:e.target.checked?{clear:true}:{}}));if(e.target.checked)setChannels(old=>old.filter(c=>c!==channel))}}/>保存时清除本渠道配置（需重新填写才能恢复）</label>
          </div></details></>}
        </section>)}
        <p className={css.note}>浏览器推送订阅暂未接入。企业微信和 Server 酱填写密钥本身；邮件使用 STARTTLS。</p>
        <button className={css.button} disabled={busy||loading||blocked||!channels.length}>{busy?'正在保存…':'保存配置'}</button>
      </form>}
      {notice&&<p role="status" className={css.note}>{notice}</p>}
      <section className={css.section}><h2>外部渠道</h2><p>{config?.external_status||'尚未读取渠道状态'}</p><p className={css.note}>配置不会修改已有委托的渠道约定。更换接收目标后，旧排队消息会被阻止，避免转发给新目标。</p></section>
      <section className={css.section}><h2>联系与回访</h2>{!loading&&!error&&!rows.length&&<p className={css.empty}>尚无投递记录。条件不成立或资料未知时，静默理由保存在委托详情。</p>}
        {rows.map(row=><article key={`${row.decision_id}:${row.channel}`} className={css.evidence}><h3>{channelLabels[row.channel]||row.channel} · {deliveryLabels[row.status]||'状态待核对'}</h3><p>{decisionText(row.decision_detail,row.reason_code)}</p><p className={css.note}>{row.detail||'等待发送前资格检查'}</p><button className={css.button} onClick={()=>visit(row.mandate_id,row.decision_id)}>回访委托与证据</button></article>)}
      </section>
    </section></main>
}
