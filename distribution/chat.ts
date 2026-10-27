import { access, mkdir, readFile, writeFile, cp } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { isDeepStrictEqual } from 'node:util'
import { join } from 'node:path'
import { spawn, type ChildProcess } from 'node:child_process'
import { createServer } from 'node:net'
import { packageRoot, request, runProcess, type Instance } from './instance.js'
import { runtimeEnvironment } from './worker.js'
import { npmCommand } from '../runtime/npm.mjs'

export const chatProfileName = 'huohuo-chat'
function sameConfig(name: string, current: string, expected: string): boolean {
  if (!name.endsWith('.json')) return current === expected
  // npm sorts dependency keys when explicitly updating a tarball dependency.
  try { return isDeepStrictEqual(JSON.parse(current), JSON.parse(expected)) } catch { return false }
}
async function chatFiles(config: Instance) {
  const directory = join(config.dsh_home, 'profiles', chatProfileName)
  const manifest = JSON.stringify({ name: 'huohuo-chat-profile', private: true,
    dependencies: { '@huohuo/research-agent': 'file:../../../product.tgz', '@huohuo/chat-bundle': 'file:./chat-bundle', '@huohuo/chat-ui': 'file:./chat-ui' },
    dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', '@huohuo/chat-bundle'] } },
  }, null, 2) + '\n'
  const patch = await readFile(join(packageRoot, 'product/bundle/chat.patch.yml'), 'utf8')
  const legacyPatch = await readFile(join(packageRoot, 'product/bundle/chat-legacy.patch.yml'), 'utf8')
  const interactionsPrevious = await readFile(join(packageRoot, 'product/bundle/chat-before-interactions.patch.yml'), 'utf8')
  const skillsPrevious = await readFile(join(packageRoot, 'product/bundle/chat-before-skills.patch.yml'), 'utf8')
  const apiKeyPrevious = await readFile(join(packageRoot, 'product/bundle/chat-before-api-key.patch.yml'), 'utf8')
  const modelMenuPrevious = await readFile(join(packageRoot, 'product/bundle/chat-before-model-menu.patch.yml'), 'utf8')
  const queryPatch = await readFile(join(packageRoot, 'product/bundle/chat-query.patch.yml'), 'utf8')
  const legacyManifest = JSON.parse(manifest)
  delete legacyManifest.dependencies['@huohuo/chat-ui']
  const bundle = JSON.stringify({ name: '@huohuo/chat-bundle', version: '1.0.0', private: true,
    dsh: { bundle: { patch: './cordis.patch.yml' } }, engines: { dsh: '0.2.1-rc.2' } }, null, 2) + '\n'
  return { directory, patch, files: [
    { name: 'package.json', content: manifest, legacy: JSON.stringify(legacyManifest, null, 2) + '\n' },
    { name: 'chat-bundle/package.json', content: bundle, legacy: bundle },
    { name: 'chat-bundle/cordis.patch.yml', content: patch, legacy: legacyPatch, previous: queryPatch, interactionsPrevious, skillsPrevious, apiKeyPrevious, modelMenuPrevious },
  ] }
}

/** Check every product-owned file before touching either profile or the installed package. */
export async function validateChatUpgrade(config: Instance): Promise<void> {
  const { directory, files } = await chatFiles(config)
  for (const { name, content, legacy, previous, interactionsPrevious, skillsPrevious, apiKeyPrevious, modelMenuPrevious } of files) {
    const path = join(directory, name)
    let current: string
    try { current = await readFile(path, 'utf8') }
    catch (error: any) { if (error.code === 'ENOENT') continue; throw error }
    if (!sameConfig(name, current, content) && !sameConfig(name, current, legacy) && !(previous && sameConfig(name, current, previous)) && !(interactionsPrevious && sameConfig(name, current, interactionsPrevious)) && !(skillsPrevious && sameConfig(name, current, skillsPrevious)) && !(apiKeyPrevious && sameConfig(name, current, apiKeyPrevious)) && !(modelMenuPrevious && sameConfig(name, current, modelMenuPrevious))) throw new Error(`聊天 Profile 已有不同配置，不覆盖：${path}`)
  }
}

export async function installChat(config: Instance, refresh = false): Promise<void> {
  await validateChatUpgrade(config)
  const { directory, patch, files } = await chatFiles(config)
  const revision = createHash('sha256').update(patch).update(await readFile(join(packageRoot, 'ui/client.js'))).digest('hex')
  await mkdir(join(directory, 'chat-bundle'), { recursive: true, mode: 0o700 })
  for (const { name, content, legacy, previous, interactionsPrevious, skillsPrevious, apiKeyPrevious, modelMenuPrevious } of files) {
    const path = join(directory, name)
    try { await writeFile(path, content, { flag: 'wx', mode: 0o600 }) }
    catch (error: any) {
      if (error.code !== 'EEXIST') throw error
      const current = await readFile(path, 'utf8')
      if (!sameConfig(name, current, content)) {
        if (!sameConfig(name, current, legacy) && !(previous && sameConfig(name, current, previous)) && !(interactionsPrevious && sameConfig(name, current, interactionsPrevious)) && !(skillsPrevious && sameConfig(name, current, skillsPrevious)) && !(apiKeyPrevious && sameConfig(name, current, apiKeyPrevious)) && !(modelMenuPrevious && sameConfig(name, current, modelMenuPrevious))) throw new Error(`聊天 Profile 已有不同配置，不覆盖：${path}`)
        await writeFile(path + '.before-chat-shell', current, { mode: 0o600, flag: 'wx' }).catch((error: NodeJS.ErrnoException) => { if (error.code !== 'EEXIST') throw error })
        await writeFile(path, content, { mode: 0o600 })
      }
    }
  }
  // Product-owned package only. User profile patch and credentials stay in place.
  await cp(join(packageRoot, 'ui'), join(directory, 'chat-ui'), { recursive: true })
  // 官方设置编辑当前 Profile patch；它是用户配置，后续启动必须保留。
  try { await writeFile(join(directory, 'cordis.patch.yml'), '[]\n', { flag: 'wx', mode: 0o600 }) }
  catch (error: any) { if (error.code !== 'EEXIST') throw error }
  try {
    const installed = JSON.parse(await readFile(join(directory, 'installed.json'), 'utf8'))
    if (refresh || installed.ui_revision !== revision) throw new Error('客户端装配需要更新')
    await access(join(directory, 'node_modules/@huohuo/research-agent/lib/product/chat/tools.js'))
    await access(join(directory, 'node_modules/@deepseek-ai/dsh/lib/bin.js'))
  } catch {
    const npm = npmCommand()
    await runProcess(npm.command, [...npm.prefix, 'install', '@huohuo/research-agent@file:../../../product.tgz', '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund', '--prefer-offline', '--cache', join(config.dsh_home, '../cache/npm')], directory)
    await writeFile(join(directory, 'installed.json'), JSON.stringify({ version: '1.0.0', complete: true, ui_revision: revision }), { mode: 0o600 })
  }
}

export async function checkChatPort(port: number): Promise<void> {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Web 端口无效')
  const server = createServer()
  await new Promise<void>((resolve, reject) => {
    server.once('error', () => reject(new Error(`本机端口 ${port} 已占用或不可用；未接管已有服务`)))
    server.listen(port, '127.0.0.1', () => server.close(() => resolve()))
  })
}

export async function launchChat(config: Instance, port = 18387, noOpen = false): Promise<ChildProcess> {
  if (port === config.port) throw new Error('聊天与后台不能使用同一端口')
  await request(config, '/health')
  await checkChatPort(port)
  const executable = join(config.dsh_home, 'profiles', chatProfileName, 'node_modules/@deepseek-ai/dsh/lib/bin.js')
  await access(executable)
  console.log(`火火 1.0.0｜DSH 原生聊天｜Profile ${chatProfileName}\n后台模型：${config.provider} / ${config.model}\n首次进入请在「设置 → 模型」配置本机凭据。关闭浏览器不会停止后台；Ctrl+C 停止本次终端服务。`)
  const child = spawn(process.execPath, [executable, '--profile', chatProfileName, '--host', '127.0.0.1', '--port', String(port), ...(noOpen ? ['--no-open'] : [])], {
    cwd: config.workspace, stdio: 'inherit',
    // 只把用户 API 能力交给聊天工具；没有 worker token、attempt token 或完整配置路径。
    env: { ...runtimeEnvironment(config), HUOHUO_CHAT_API: `http://127.0.0.1:${config.port}`, HUOHUO_USER_TOKEN: config.user_token, HUOHUO_CHAT_WEB_ORIGIN: `http://127.0.0.1:${port}` },
  })
  await new Promise<void>((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject) })
  return child
}

export async function stopChat(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return
  const exited = new Promise<void>(resolve => child.once('exit', () => resolve()))
  child.kill('SIGTERM')
  const timeout = setTimeout(() => child.kill('SIGKILL'), 3000)
  await exited; clearTimeout(timeout)
}
