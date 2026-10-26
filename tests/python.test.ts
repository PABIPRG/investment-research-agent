import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { resolvePython } from '../runtime/python.mjs'

const macPair = existsSync('/usr/bin/python3') && existsSync('/opt/homebrew/bin/python3')
test('PATH 首个 Python 过旧时选择已安装的兼容解释器并返回绝对路径', { skip: !macPair }, async () => {
  const value = await resolvePython({ explicit: '', candidates: ['/usr/bin/python3', '/opt/homebrew/bin/python3'] })
  assert.ok(value.checked.some(value => value.includes('3.9.6')))
  assert.match(value.executable, /^\/opt\/homebrew\//)
  assert.match(value.version, /^3\.(1[1-9]|[2-9]\d)\./)
})
test('显式指定不兼容解释器时给出版本，不能静默换用另一个', { skip: !macPair }, async () => {
  await assert.rejects(resolvePython({ explicit: '/usr/bin/python3', candidates: ['/opt/homebrew/bin/python3'] }), /已指定 HUOHUO_PYTHON[\s\S]*3\.9\.6/)
})
test('没有解释器时错误包含准确候选和修复入口', async () => {
  await assert.rejects(resolvePython({ explicit: '', candidates: ['/huohuo-no-such-python'] }), /huohuo-no-such-python[\s\S]*HUOHUO_PYTHON=/)
})
