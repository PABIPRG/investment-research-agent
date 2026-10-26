/** 隔离 UAT 模型替身：实际调用产品工具，不写数据库。 */
import type { Context } from '@deepseek-ai/cordis'
import { LlmAdapter,ToolCallId,type GenerateOptions,type StreamChunk } from '@deepseek-ai/dsh-llm'
export const inject=['llm']
export function apply(ctx:Context){
 class Fixture extends LlmAdapter{
  async listModels(route:string){return [{provider:route,id:'mandate-uat',name:'委托验收替身',inputModalities:['text' as const]}]}
  async resolveModel(route:string,id:string){return {provider:route,id,name:'委托验收替身',inputModalities:['text' as const],context:{contextWindow:128000},defaultMaxTokens:2048}}
  async *stream(options:GenerateOptions):AsyncIterable<StreamChunk>{
   const tool=options.messages.findLast(m=>m.role==='tool')
   let text='委托验收'
   if(options.purpose!=='session-title'){
    if(!tool){
     const id=ToolCallId('mandate-create-uat'),name='ask_user_question';const args=JSON.stringify({timeout:-1,questions:[{id:'security',header:'确认对象',question:'请选择要研究的证券（本轮为合成验收选项）。',options:[{label:'科士达 · 002518 · 深市',description:'只确认研究对象，尚不创建委托。'},{label:'重新搜索',description:'更换关键词后重新查询。'}]}]})
     yield {type:'block-start',index:0,blockType:'tool-call'};yield {type:'tool-call-delta',index:0,id,name,argumentsDelta:args};yield {type:'block-end',index:0,block:{type:'tool-call',id,name,arguments:args}};yield {type:'finish',reason:{kind:'tool-calls'}};return
    }
    text='已收到原生选项回答；尚未创建委托。'+tool.content.filter(x=>x.type==='text').map(x=>x.text).join('')
   }
   yield {type:'block-start',index:0,blockType:'text'};yield {type:'text-delta',index:0,text};yield {type:'block-end',index:0,block:{type:'text',text}};yield {type:'finish',reason:{kind:'stop'}}
  }
 }
 ctx.llm.registerAdapter(['huohuo-question-uat'],new Fixture())
}
