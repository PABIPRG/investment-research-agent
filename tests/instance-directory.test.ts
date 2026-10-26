import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createInstanceDirectory } from '../distribution/instance.js'

test('首次安装创建缺失的父目录，重复初始化拒绝且保留实例数据', async () => {
  const temp = await mkdtemp(join(tmpdir(), 'huohuo-init-'))
  try {
    const target = join(temp, '.instance', 'entity-review')
    assert.equal(await createInstanceDirectory(target), target)
    await writeFile(join(target, 'instance.json'), 'preserved')
    await assert.rejects(createInstanceDirectory(target), { code: 'EEXIST' })
    assert.equal(await readFile(join(target, 'instance.json'), 'utf8'), 'preserved')
  } finally { await rm(temp, { recursive: true, force: true }) }
})
