import assert from 'node:assert/strict'
import {test} from 'node:test'
import {companionMotion} from '../product/ui/companion-state.js'
test('真实待回答状态优先于运行和草稿，结束后回到当前输入状态',()=>{
 assert.equal(companionMotion({pending:true,running:true,streaming:true,draft:'请继续'}),'awaiting_reply')
 assert.equal(companionMotion({running:true,streaming:true}),'speaking')
 assert.equal(companionMotion({running:true,draft:'草稿'}),'thinking')
 assert.equal(companionMotion({draft:'草稿'}),'listening')
 assert.equal(companionMotion({draft:'  '}),'idle')
 assert.equal(companionMotion({}),'idle')
})
