import assert from 'node:assert/strict'
import {test} from 'node:test'
import {companionMotion} from '../product/ui/companion-state.js'
import { conversationActivity } from '../product/ui/shell/companion-feedback.js'
test('真实待回答状态优先于运行和草稿，结束后回到当前输入状态',()=>{
 assert.equal(companionMotion({pending:true,running:true,streaming:true,draft:'请继续'}),'awaiting_reply')
 assert.equal(companionMotion({running:true,streaming:true}),'speaking')
 assert.equal(companionMotion({running:true,draft:'草稿'}),'thinking')
 assert.equal(companionMotion({draft:'草稿'}),'listening')
 assert.equal(companionMotion({draft:'  '}),'idle')
 assert.equal(companionMotion({}),'idle')
})
test('DSH实时推理、正文与工具派发分别映射，不用历史文本或笼统流式标记猜测',()=>{
 assert.equal(conversationActivity({partial:{blocks:[{kind:'reasoning',text:'正在比较'}]},runningCalls:[]}), 'thinking')
 assert.equal(conversationActivity({partial:{blocks:[{kind:'reasoning',text:'已比较'},{kind:'text',text:'结论'}]},runningCalls:[]}), 'speaking')
 assert.equal(conversationActivity({partial:{blocks:[{kind:'text',text:''}]},runningCalls:[]}), undefined)
 assert.equal(conversationActivity({partial:{blocks:[{kind:'tool-call',name:'query_market'}]},runningCalls:[{phase:'preparing'}]}), 'thinking')
 assert.equal(conversationActivity({partial:null,runningCalls:[{phase:'start'}]}), 'working')
 assert.equal(conversationActivity({partial:null,runningCalls:[]}), undefined)
 assert.equal(conversationActivity({partial:{unexpected:true},runningCalls:[null]}), undefined)
})
test('工具整理资料独立于思考，待用户回答优先于后台调用',()=>{
 assert.equal(companionMotion({running:true,working:true}),'working')
 assert.equal(companionMotion({running:true,working:true,pending:true}),'awaiting_reply')
 assert.equal(companionMotion({running:true,working:true,streaming:true}),'working')
 assert.equal(companionMotion({running:false,working:true}),'idle')
})
