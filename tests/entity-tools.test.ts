import test from 'node:test'
import assert from 'node:assert/strict'
import {confirmationQuestions,choicesFromAnswer} from '../product/chat/entity-tools.js'
const candidate={entity_id:'SEC:CN:A:002518',entity_type_code:'ENTITY_01_01',canonical_name:'科士达'}
const snapshot={mentions:[{mention_id:'m1',raw_text:'科士达',candidates:[candidate]}]}
test('原生确认只能映射唯一精确选项，文字声明/自由输入/跳过不确认',()=>{
 const label=confirmationQuestions(snapshot)[0].options[0].label
 assert.deepEqual(choicesFromAnswer(snapshot,{answers:[{id:'m1',selected:[label]}]}),{m1:candidate.entity_id})
 for(const answer of [{answers:[{id:'m1',selected:[]}]},{answers:[{id:'m1',selected:[label],custom:'不是这个'}]},{answers:[{id:'m1',selected:['已确认']}]},{pending:true},{answers:[{id:'m1',selected:[label]},{id:'m1',selected:[label]}]}])assert.deepEqual(choicesFromAnswer(snapshot,answer),{})
})
