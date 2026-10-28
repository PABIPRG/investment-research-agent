import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import {businessApi,businessTool,confirmBusiness,cancelled,versionField,channelsField,type Ask} from './business-tools.js'
export const notificationToolNames=['read_notification_settings','list_notification_deliveries','update_notification_preferences','clear_notification_channel']
const labels:Record<string,string>={app:'应用内',wecom:'企业微信',serverchan:'Server 酱',email:'邮件'}
export function publicSettings(config:any){
 return {revision:config.revision,enabled:config.enabled,channels:config.channels,timezone:config.timezone,quiet_hours:config.quiet_hours,external_status:config.external_status,external:Object.fromEntries(Object.entries(config.external||{}).map(([k,v]:[string,any])=>[k,{configured:!!v.configured,secret_saved:v.secret_saved}]))}
}
export function createNotificationTools(address:string,token:string,ask?:Ask):ToolDefinition[]{
 const api=businessApi(address,token)
 return [
  businessTool('read_notification_settings','读取脱敏通知配置、渠道是否配置和静默时段；不读取密钥，不证明真实送达。',{},[],async(_a,e)=>({ok:true,data:publicSettings(await api('/notifications/config',e))})),
  businessTool('list_notification_deliveries','读取当前用户投递状态和回访委托引用。accepted 不等于 delivered，unknown 不能自动重发。',{},[],async(_a,e)=>({ok:true,data:await api('/notifications',e)})),
  businessTool('update_notification_preferences','修改提醒开关、已配置渠道、时区和每日静默；程序读取前值并要求真实用户确认。不会扩大委托授权或发送测试消息，不接受密钥和接收目标。',{
   expected_revision:versionField,enabled:{type:'boolean'},channels:channelsField,timezone:{type:'string',minLength:1,maxLength:100},quiet_hours:{anyOf:[{type:'null'},{type:'object',properties:{start:{type:'string',pattern:'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$'},end:{type:'string',pattern:'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$'}},required:['start','end'],additionalProperties:false}]}
  },['expected_revision','enabled','channels','timezone','quiet_hours'],async(a,e)=>{
   const c=await api('/notifications/config',e)
   if(c.revision!==a.expected_revision)throw new Error('配置版本已变化，请刷新核对')
   if(a.channels.some((ch:string)=>ch!=='app'&&!c.external?.[ch]?.configured))throw new Error('渠道未配置，请先到消推配置的安全表单填写')
   const quiet=(q:any)=>q?`${q.start}–${q.end}${q.start===q.end?'（全天静默）':''}`:'不设置静默'
   if(!await confirmBusiness(ask,e,`保存联系偏好？\n提醒：${c.enabled?'启用':'关闭'} → ${a.enabled?'启用':'关闭'}\n渠道：${c.channels.map((x:string)=>labels[x]).join('、')} → ${a.channels.map((x:string)=>labels[x]).join('、')}\n时区：${c.timezone} → ${a.timezone}\n静默：${quiet(c.quiet_hours)} → ${quiet(a.quiet_hours)}\n不会改变已有委托的渠道授权。关闭会阻止尚未开始的发送，在途请求无法撤回。`))return cancelled
   return {ok:true,data:publicSettings(await api('/notifications/config',e,a))}
  },true),
  businessTool('clear_notification_channel','清除指定外部渠道的已保存凭据和目标；原生确认后执行。不可恢复，需在安全表单重新配置；不修改其它渠道。',{
   channel:{type:'string',enum:['wecom','serverchan','email']},expected_revision:versionField
  },['channel','expected_revision'],async(a,e)=>{
   const c=await api('/notifications/config',e)
   if(c.revision!==a.expected_revision)throw new Error('配置版本已变化，请刷新')
   const channels=c.channels.filter((x:string)=>x!==a.channel);if(!channels.length)channels.push('app')
   if(!await confirmBusiness(ask,e,`清除${labels[a.channel]}的凭据和接收目标，并从启用渠道移除？需要重新填写才能恢复。保留渠道：${channels.map((x:string)=>labels[x]).join('、')}。已在途请求无法撤回。`))return cancelled
   return {ok:true,data:publicSettings(await api('/notifications/config',e,{expected_revision:c.revision,enabled:c.enabled,timezone:c.timezone,quiet_hours:c.quiet_hours,channels,external:{[a.channel]:{clear:true}}}))}
  },true)
 ]
}
