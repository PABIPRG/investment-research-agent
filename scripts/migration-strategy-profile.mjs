// 组合 UAT 复用正式隔离 Profile，模型仅接受明确合成来源。
import { mkdir, writeFile, readdir, symlink, copyFile, realpath } from 'node:fs/promises'
import { join } from 'node:path'

export async function prepareMigrationStrategyProfile(root, config) {
  const profile = join(config.dsh_home, 'profiles/huohuo-strategy-worker')
  const modules = join(profile, 'node_modules')
  await mkdir(join(modules, '@huohuo'), { recursive: true })
  async function link(source, target) {
    try { await symlink(source, target, 'dir') }
    catch (error) {
      if (error.code !== 'EEXIST' || await realpath(source) !== await realpath(target)) throw error
    }
  }
  for (const entry of await readdir(join(root, 'node_modules'))) {
    if (entry !== '@huohuo') await link(join(root, 'node_modules', entry), join(modules, entry))
  }
  await link(root, join(modules, '@huohuo/research-agent'))
  const bundle = join(profile, 'strategy-bundle')
  await mkdir(bundle, { recursive: true })
  await writeFile(join(bundle, 'package.json'), JSON.stringify({
    name: '@huohuo/strategy-bundle', version: '1.0.0', private: true,
    engines: { dsh: '0.2.1-rc.2' }, dsh: { bundle: { patch: './cordis.patch.yml' } },
  }))
  await copyFile(join(root, 'product/profile/huohuo-strategy-worker.yml'), join(bundle, 'cordis.patch.yml'))
  await link(bundle, join(modules, '@huohuo/strategy-bundle'))
  await writeFile(join(profile, 'package.json'), JSON.stringify({
    name: 'huohuo-migration-strategy-profile', private: true,
    dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-sdk-app', '@huohuo/strategy-bundle'] } },
  }))
  await writeFile(join(profile, 'cordis.patch.yml'), `- id: llm-deepseek
  disabled: true
- id: llm-deepseek-account
  disabled: true
- id: llm-pi-ai
  disabled: true
- insert:
    - id: strategy-runtime-model
      name: ${JSON.stringify(join(root, 'lib/tests/strategy-runtime-model.js'))}
      config:
        proofPath: ${JSON.stringify(join(config.workspace, 'strategy-proof.jsonl'))}
`, { mode: 0o600 })
}
