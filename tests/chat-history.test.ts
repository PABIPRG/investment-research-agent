import assert from 'node:assert/strict'
import { test } from 'node:test'
import { historyRows, type ChatSummary } from '../product/ui/history.js'

test('历史不泄漏目录、归档、后台子代理或未选中的空会话，分支对话保留', () => {
  const make = (id: string, extra = {}): ChatSummary => ({ id, blank: false, running: false, updatedAt: 1, projectionValues: { agentPreset: 'huohuo' }, ...extra })
  const rows = [make('old', { title: '旧对话' }), make('fork', { parentId: 'old', updatedAt: 4 }),
    make('sub', { origin: 'subagent' }), make('worker', { projectionValues: {} }), make('foreign', { projectionValues: { agentPreset: 'standard' } }),
    make('archived'), make('blank', { blank: true }), make('current', { blank: true, updatedAt: 5 })]
  assert.deepEqual(historyRows({ ids: rows.map(x => x.id), byId: Object.fromEntries(rows.map(x => [x.id, x])), phase: 'ready' }, ['archived'], 'current').map(x => [x.id, x.label]),
    [['current', '新对话'], ['fork', '未命名对话'], ['old', '旧对话']])
})

test('等待会话与归档两个基线，避免归档记录短暂进入列表', () => {
  const row: ChatSummary = { id: 'private-archive', title: '已归档', blank: false, running: false, updatedAt: 1, projectionValues: { agentPreset: 'huohuo' } }
  const catalog = { ids: [row.id], byId: { [row.id]: row }, phase: 'ready' as const }
  assert.deepEqual(historyRows(catalog, [], undefined, false), [])
  assert.deepEqual(historyRows({ ...catalog, phase: 'pending' }, [], undefined, true), [])
  assert.deepEqual(historyRows(catalog, [row.id], undefined, true), [])
})
