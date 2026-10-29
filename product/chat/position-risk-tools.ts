import type {ToolDefinition} from '@deepseek-ai/dsh-tools'
import {businessApi,businessTool} from './business-tools.js'
export const positionRiskToolNames=['preview_position_risk_change','read_investment_risk']
const target={type:'object',additionalProperties:false,properties:{enabled:{type:'boolean'},mode:{type:'string',enum:['percent','price']},value:{type:['number','null'],minimum:0,maximum:1e12}},required:['enabled','mode','value']}
const nullableTime={type:['string','null'],maxLength:100}
const config={type:'object',additionalProperties:false,properties:{take_profit:target,stop_loss:target,effective_at:nullableTime,expires_at:nullableTime,monitoring_disabled:{type:'boolean'}},required:['take_profit','stop_loss','effective_at','expires_at','monitoring_disabled']}
export function createPositionRiskTools(address:string,token:string):ToolDefinition[]{
  const api=businessApi(address,token)
  return [businessTool('preview_position_risk_change','预览持仓风险全局百分比、单仓百分比/绝对价覆盖、删除覆盖或重新布防。先读 read_investment_facts 的 position_risk；成本冻结于激活快照，不自动随成本移动。global/override 传完整 config，其他操作不传 config。percent 用小数（8%=0.08）。保存须 commit_investment_change 原生确认，会建立/替换正式价格委托，仅应用内联系一次，不交易。',
    {operation:{type:'string',enum:['global','override','remove_override','rearm']},ticker:{type:'string',pattern:'^[0-9]{6}$'},kind:{type:'string',enum:['take_profit','stop_loss']},config},['operation'],async(a,e)=>({ok:true,data:await api('/investment/preview',e,{command:'position_risk',payload:a})})),
    businessTool('read_investment_risk','读取旧版等权组合风险、画像预算、影子净值回撤/波动及组合/影子/事件/画像/持仓计划聚合预警。未录入与空仓不同，默认稳健预算不是已确认画像，等权和影子代理不是账户实际市值或收益。读取不发通知；事件为本机保存快照。',{},[],async(_a,e)=>({ok:true,data:await api('/personalization/risk',e,{})}))]
}
