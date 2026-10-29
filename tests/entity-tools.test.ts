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

test('同一讨论对象只问一次，答案只提交对象组，不展开原文提及',()=>{
 const grouped={mentions:[{mention_id:'name',raw_text:'平安银行',candidates:[candidate]},{mention_id:'code',raw_text:'000001',candidates:[candidate]}],discussion_subjects:[{subject_id:'subject-1',raw_text:'平安银行 / 000001',mention_ids:['name','code'],primary_entity_id:candidate.entity_id,candidates:[candidate]}]}
 const questions=confirmationQuestions(grouped)
 assert.equal(questions.length,1)
 assert.equal(questions[0].id,'subject-1')
 assert.deepEqual(choicesFromAnswer(grouped,{answers:[{id:'subject-1',selected:[questions[0].options[0].label]}]}),{'subject-1':candidate.entity_id})
 assert.deepEqual(choicesFromAnswer(grouped,{answers:[{id:'name',selected:[questions[0].options[0].label]}]}),{})
 assert.equal(confirmationQuestions({...grouped,discussion_subjects:[{...grouped.discussion_subjects[0],confirmation:{confirmation_id:'saved'}}]}).length,0)
})
