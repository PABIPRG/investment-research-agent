/** 共用受控业务桥：身份不由模型填写，确认来自原生问答。 */
import type { ToolDefinition, ToolRunContext } from '@deepseek-ai/dsh-tools'
import { createHash } from 'node:crypto'
export type Ask = (questions: unknown[], exec: ToolRunContext) => Promise<any>
export const textField = {type:'string',minLength:1,maxLength:2000}
export const versionField = {type:'integer',minimum:0}
export const channelsField = {type:'array',minItems:1,maxItems:4,uniqueItems:true,items:{type:'string',enum:['app','wecom','serverchan','email']}}
export const cancelled = {ok:true,saved:false,confirmed:false,guidance:'未确认，未保存任何变更。'}
export function requestKey(exec: ToolRunContext, purpose: string) {
  if (!exec.agent?.session.id || !exec.callId) throw new Error('缺少可信会话与调用身份')
  return 'chat:'+createHash('sha256').update(JSON.stringify([exec.agent.session.id,exec.callId,purpose])).digest('hex')
}
export function businessApi(address: string, token: string) {
  const base=new URL(address)
  if(base.protocol!=='http:'||base.hostname!=='127.0.0.1'||!base.port||base.pathname!=='/'||base.username||base.password||base.search||base.hash||!token)throw new Error('业务 API 配置无效')
  return async(path:string,exec:ToolRunContext,body?:unknown):Promise<any>=>{
    try {
      const r=await fetch(new URL(path,base),{method:body===undefined?'GET':'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),redirect:'error',signal:AbortSignal.any([exec.signal,AbortSignal.timeout(15000)])})
      const data=await r.json() as any
      if(!r.ok)throw Object.assign(new Error(data.detail||'业务操作失败'),{http_status:r.status})
      return data
    }catch(e){
      if((e as any).http_status)throw e
      throw Object.assign(new Error(body===undefined?'读取失败，不代表空数据。':'提交结果未知。先读取事实或回执核对，不要重复提交。'),{code:body===undefined?'backend_unavailable':'submission_unknown'})
    }
  }
}
// 不依赖模型遵守 schema；直接调用同样拒绝额外字段、类型错误和越界。
export function validate(schema:any,value:any):void {
  if(schema.anyOf){if(!schema.anyOf.some((s:any)=>{try{validate(s,value);return true}catch{return false}}))throw new Error('参数格式无效');return}
  const type=value===null?'null':Array.isArray(value)?'array':typeof value
  if(schema.type==='integer'? !Number.isSafeInteger(value):schema.type && !(Array.isArray(schema.type)?schema.type:[schema.type]).includes(type))throw new Error('参数类型无效')
  if(schema.enum&&!schema.enum.includes(value))throw new Error('参数选项无效')
  if(type==='object'){
    if(schema.additionalProperties===false&&Object.keys(value).some(k=>!Object.hasOwn(schema.properties||{},k)))throw new Error('包含未允许字段')
    for(const k of schema.required||[])if(!Object.hasOwn(value,k))throw new Error('缺少必要字段：'+k)
    for(const [k,v]of Object.entries(value))if(schema.properties?.[k])validate(schema.properties[k],v)
  }
  if(type==='string'&&((schema.minLength!==undefined&&value.length<schema.minLength)||(schema.maxLength!==undefined&&value.length>schema.maxLength)||(schema.pattern&&!new RegExp(schema.pattern).test(value))))throw new Error('文本格式无效')
  if(type==='number'&&(!Number.isFinite(value)||(schema.minimum!==undefined&&value<schema.minimum)||(schema.exclusiveMinimum!==undefined&&value<=schema.exclusiveMinimum)||(schema.maximum!==undefined&&value>schema.maximum)))throw new Error('数值越界')
  if(type==='array'){
    if((schema.minItems!==undefined&&value.length<schema.minItems)||(schema.maxItems!==undefined&&value.length>schema.maxItems)||(schema.uniqueItems&&new Set(value).size!==value.length))throw new Error('列表参数无效')
    if(schema.items)for(const v of value)validate(schema.items,v)
  }
}
export function businessTool(name:string,description:string,properties:Record<string,any>,required:string[],run:(args:any,exec:ToolRunContext)=>Promise<any>,interactive=false):ToolDefinition {
  const parameters={type:'object',properties,required,additionalProperties:false}
  return {name,description,parameters,timeoutMs:interactive?2147483000:30000,output:{schema:{type:'object',additionalProperties:true},render:(_a,v)=>[{type:'text',text:JSON.stringify(v)}]},async execute(input,exec){
    requestKey(exec,name);validate(parameters,input)
    try{return await run(input,exec)}catch(e){return {ok:false,error:(e as any).code||'business_operation_failed',http_status:(e as any).http_status,detail:(e as Error).message}}
  }}
}
export async function confirmBusiness(ask:Ask|undefined,exec:ToolRunContext,question:string):Promise<boolean>{
  if(!ask)throw new Error('原生确认未接通，不能保存')
  const result=await ask([{id:'business-confirm',header:'保存前确认',question,options:[{label:'确认执行',description:'按上述内容保存；以实际业务回执为准。'},{label:'取消',description:'保留现有业务状态，不提交本次修改。'}]}],exec)
  if(result?.pending||result?.cancelled||!Array.isArray(result?.answers)||result.answers.length!==1)return false
  const a=result.answers[0]
  return a.id==='business-confirm'&&!a.custom&&Array.isArray(a.selected)&&a.selected.length===1&&a.selected[0]==='确认执行'
}
