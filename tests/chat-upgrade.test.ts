import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { installChat, validateChatUpgrade } from '../distribution/chat.js'
import { packageRoot, type Instance } from '../distribution/instance.js'

for (const baseline of ['chat-legacy.patch.yml', 'chat-query.patch.yml', 'chat-before-interactions.patch.yml', 'chat-before-skills.patch.yml', 'chat-before-api-key.patch.yml', 'chat-before-model-menu.patch.yml', 'startup-key-onboarding']) test(`${baseline} 升级先完整预检，再迁移受管文件并保留用户状态`, async () => {
  const temp = await mkdtemp(join(tmpdir(), 'huohuo-upgrade-'))
  const config = { dsh_home: join(temp, 'dsh') } as Instance
  const profile = join(config.dsh_home, 'profiles/huohuo-chat')
  const manifest = JSON.stringify({ name: 'huohuo-chat-profile', private: true,
    dependencies: { '@huohuo/research-agent': 'file:../../../product.tgz', '@huohuo/chat-bundle': 'file:./chat-bundle', ...(baseline !== 'chat-legacy.patch.yml' ? { '@huohuo/chat-ui': 'file:./chat-ui' } : {}) },
    dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', '@huohuo/chat-bundle'] } },
  }, null, 2) + '\n'
  const legacy = baseline === 'startup-key-onboarding'
    ? (await readFile(join(packageRoot, 'product/bundle/chat.patch.yml'), 'utf8')).replace('credentialOnboarding: false', 'credentialOnboarding: true')
    : await readFile(join(packageRoot, 'product/bundle', baseline), 'utf8')
  const patch = await readFile(join(packageRoot, 'product/bundle/chat.patch.yml'), 'utf8')
  try {
    await mkdir(join(profile, 'chat-bundle'), { recursive: true })
    await writeFile(join(profile, 'package.json'), manifest)
    await writeFile(join(profile, 'chat-bundle/cordis.patch.yml'), 'user-modified-bundle')
    await writeFile(join(profile, 'cordis.patch.yml'), 'user-model-config\n')
    await writeFile(join(temp, 'business.sqlite3'), 'untouched-database')
    await assert.rejects(() => installChat(config), /不覆盖/)
    assert.equal(await readFile(join(profile, 'package.json'), 'utf8'), manifest)
    await assert.rejects(() => readFile(join(profile, 'chat-bundle/package.json')), { code: 'ENOENT' })
    await writeFile(join(profile, 'chat-bundle/cordis.patch.yml'), legacy)
    await validateChatUpgrade(config)
    // Pre-existing dependency sentinels isolate file migration from npm/network.
    for (const path of ['@huohuo/research-agent/lib/product/chat/tools.js', '@deepseek-ai/dsh/lib/bin.js']) {
      const file = join(profile, 'node_modules', path)
      await mkdir(join(file, '..'), { recursive: true }); await writeFile(file, '')
    }
    const ui_revision = createHash('sha256').update(patch).update(await readFile(join(packageRoot, 'ui/client.js'))).digest('hex')
    await writeFile(join(profile, 'installed.json'), JSON.stringify({ ui_revision }))
    await installChat(config)
    if (baseline === 'chat-legacy.patch.yml') assert.equal(await readFile(join(profile, 'package.json.before-chat-shell'), 'utf8'), manifest)
    const installed = JSON.parse(await readFile(join(profile, 'package.json'), 'utf8'))
    installed.dependencies = Object.fromEntries(Object.entries(installed.dependencies).sort(([a], [b]) => a.localeCompare(b)))
    const sorted = JSON.stringify(installed, null, 2) + '\n'
    await writeFile(join(profile, 'package.json'), sorted)
    await installChat(config)
    assert.equal(await readFile(join(profile, 'package.json'), 'utf8'), sorted)
    installed.dependencies['user-plugin'] = '1.0.0'
    await writeFile(join(profile, 'package.json'), JSON.stringify(installed))
    await assert.rejects(() => validateChatUpgrade(config), /不覆盖/)
    await writeFile(join(profile, 'package.json'), sorted)
    assert.equal(await readFile(join(profile, 'chat-bundle/cordis.patch.yml.before-chat-shell'), 'utf8'), legacy)
    assert.equal(await readFile(join(profile, 'chat-bundle/cordis.patch.yml'), 'utf8'), patch)
    assert.equal(await readFile(join(profile, 'cordis.patch.yml'), 'utf8'), 'user-model-config\n')
    assert.equal(await readFile(join(temp, 'business.sqlite3'), 'utf8'), 'untouched-database')
    await installChat(config)
    assert.equal(await readFile(join(profile, 'chat-bundle/cordis.patch.yml.before-chat-shell'), 'utf8'), legacy)
  } finally { await rm(temp, { recursive: true, force: true }) }
})

test('正常启动不弹密钥引导，保留模型设置和选择入口；回放只由测试启动器替换', async () => {
  const patch = await readFile(join(packageRoot, 'product/bundle/chat.patch.yml'), 'utf8')
  for (const id of ['ui-settings-account', 'account-controller', 'llm-deepseek-account', 'deepseek-account']) assert.ok(patch.includes(`- id: ${id}\n  disabled: true`), id)
  assert.ok(patch.includes('credentialOnboarding: false'))
  assert.ok(patch.includes('- id: ui-model-selection\n  disabled: false'))
  assert.ok(patch.includes('- id: ui-commands\n  disabled: false'))
  assert.ok(!patch.includes('controlled-chat-model'))
  assert.ok(!patch.includes('- id: llm-deepseek\n  disabled: true'))
  const smoke = await readFile(join(packageRoot, 'scripts/smoke-skills.mjs'), 'utf8')
  assert.ok(smoke.includes('credentialOnboarding: false'))
  assert.ok(smoke.includes('仅接受回放编号'))
})
