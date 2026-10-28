/** 单独装配策略 DSH；不继承研究执行器和任何写入工具。 */
import { mkdir, readFile, writeFile, access } from 'node:fs/promises'
import { join } from 'node:path'
import { isDeepStrictEqual } from 'node:util'
import { packageRoot, runProcess, type Instance } from './instance.js'
import { npmCommand } from '../runtime/npm.mjs'
async function profileFiles(config: Instance) {
  const directory = join(config.dsh_home, 'profiles', 'huohuo-strategy-worker')
  const files = {
    'package.json': JSON.stringify({ name: 'huohuo-strategy-profile', private: true,
      dependencies: { '@huohuo/research-agent': 'file:../../../product.tgz', '@huohuo/strategy-bundle': 'file:./strategy-bundle' },
      dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-sdk-app', '@huohuo/strategy-bundle'] } } }, null, 2) + '\n',
    'strategy-bundle/package.json': JSON.stringify({ name: '@huohuo/strategy-bundle', version: '1.0.0', private: true,
      engines: { dsh: '0.2.1-rc.2' }, dsh: { bundle: { patch: './cordis.patch.yml' } } }, null, 2) + '\n',
    'strategy-bundle/cordis.patch.yml': await readFile(join(packageRoot, 'product/profile/huohuo-strategy-worker.yml'), 'utf8'),
  }
  // 自定义配置不静默覆盖，先检查所有文件。
  for (const [name, content] of Object.entries(files)) {
    try {
      const current = await readFile(join(directory, name), 'utf8')
      const equal = name.endsWith('.json') ? isDeepStrictEqual(JSON.parse(current), JSON.parse(content)) : current === content
      if (!equal) throw Error(`策略 Profile 存在不同配置，未覆盖：${name}`)
    } catch (error: any) { if (error.code !== 'ENOENT') throw error }
  }
  return { directory, files }
}
export async function validateStrategyUpgrade(config: Instance): Promise<void> { await profileFiles(config) }
export async function installStrategyProfile(config: Instance, refresh = false): Promise<void> {
  const { directory, files } = await profileFiles(config)
  await mkdir(join(directory, 'strategy-bundle'), { recursive: true, mode: 0o700 })
  for (const [name, content] of Object.entries(files)) {
    try { await writeFile(join(directory, name), content, { flag: 'wx', mode: 0o600 }) }
    catch (error: any) { if (error.code !== 'EEXIST') throw error }
  }
  try { await writeFile(join(directory, 'cordis.patch.yml'), '[]\n', { flag: 'wx', mode: 0o600 }) }
  catch (error: any) { if (error.code !== 'EEXIST') throw error }
  const npm = npmCommand()
  await runProcess(npm.command, [...npm.prefix, 'install', ...(refresh ? ['@huohuo/research-agent@file:../../../product.tgz'] : []), '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund', '--prefer-offline', '--cache', join(config.dsh_home, '../cache/npm')], directory)
  await access(join(directory, 'node_modules/@huohuo/research-agent/lib/product/strategy-worker.js'))
}
