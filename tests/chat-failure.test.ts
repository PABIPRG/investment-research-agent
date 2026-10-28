import test from 'node:test'
import assert from 'node:assert/strict'
import { canFoldProcess, failureCopy } from '../product/ui/shell/failure-model.js'
test('缺少模型凭据提供配置路径，未知错误不误导为密钥问题', () => {
  assert.equal(failureCopy('MISSING_CREDENTIAL').configure, true)
  assert.match(failureCopy('MISSING_CREDENTIAL').detail, /设置 → 模型/)
  assert.equal(failureCopy('NETWORK_UNKNOWN').configure, false)
  assert.equal(failureCopy('INTERRUPTED').title, '这次回答已停止')
  assert.match(failureCopy().detail, /不会自动重试/)
})

test('有内容的原生过程保留所有可展开的终止状态', () => {
  for (const reason of ['completed', 'blocked', 'max-tokens', 'forked'])
    assert.equal(canFoldProcess(true, reason), true)
  for (const reason of ['error', 'aborted', 'interrupted'])
    assert.equal(canFoldProcess(true, reason), false)
  assert.equal(canFoldProcess(false, 'completed'), false)
})
