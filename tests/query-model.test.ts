import assert from 'node:assert/strict'
import { test } from 'node:test'
import { read, safeSource } from '../product/ui/model.js'

test('拒绝会导致 React 崩溃的行情和结果字段，且外部链接不执行脚本', async () => {
  const previous = globalThis.fetch
  const signal = new AbortController().signal
  try {
    for (const row of [
      { values: { name: { html: '<img>' } } }, { limitations: [{}] }, { source: {} }, { data_as_of: [] },
    ]) {
      globalThis.fetch = async () => Response.json([{ evidence_id: 'e', attempt_id: 'a', status: 'ok', source: 'fixture', ...row }])
      await assert.rejects(read('evidence', signal, 'id'), /格式/)
    }
    const execution = { execution_id: 'id', scope: { entity_id: 'SEC:CN:A:600519' }, question: 'q', status: 'succeeded', created_at: 1, updated_at: 2, revision: 1 }
    for (const result of [{ summary: {} }, { error: [] }, { evidence_ids: 'bad' }]) {
      globalThis.fetch = async () => Response.json({ ...execution, result })
      await assert.rejects(read('execution', signal, 'id'), /格式/)
    }
    assert.equal(safeSource('javascript:alert(1)'), undefined)
    assert.equal(safeSource('https://user:secret@example.com/'), undefined)
    assert.equal(safeSource('https://example.com/evidence'), 'https://example.com/evidence')
  } finally { globalThis.fetch = previous }
})
