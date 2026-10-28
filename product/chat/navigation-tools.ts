import {businessApi,businessTool,textField} from './business-tools.js'
export const navigationToolNames=['open_product_view']
export function createNavigationTools(address:string,token:string,webOrigin=process.env.HUOHUO_CHAT_WEB_ORIGIN){
 const api=businessApi(address,token)
 return [businessTool('open_product_view','生成本产品页面入口，用户点击链接进入；可定位属于当前用户的委托。仅导航，不修改业务；模型或渠道凭据在安全表单填写。',{
  view:{type:'string',enum:['chat','mandates','investment','notifications','activity','evolution','settings']},mandate_id:{...textField,pattern:'^MND_[a-f0-9]{32}$'}
 },['view'],async(a,e)=>{
  if(a.mandate_id){if(a.view!=='mandates')throw new Error('只有委托页支持委托定位');await api('/mandates/'+a.mandate_id,e)}
  if(a.view==='settings')return {ok:true,view:'settings',navigation_required:true,guidance:'请点击顶部账号菜单中的「设置」→「模型」进入原生 API Key 表单；当前 DSH 未公开设置打开 API。不要在聊天中填写模型密钥。'}
  if(!webOrigin||!/^http:\/\/127\.0\.0\.1:\d+$/.test(webOrigin))throw new Error('当前聊天未配置页面入口，请使用顶部导航')
  const labels:Record<string,string>={chat:'对话',mandates:'我的委托',investment:'持仓与自选',notifications:'提醒方式',settings:'设置',activity:'动态',evolution:'验证与演进'}
  return {ok:true,view:a.view,url:webOrigin+'/#huohuo-view='+a.view+(a.mandate_id?'&mandate='+a.mandate_id:''),label:'打开'+labels[a.view],guidance:'将入口作为可点击链接提供给用户；用户点击后打开页面。尚未代替用户保存或填写任何内容。'}
 })]
}
