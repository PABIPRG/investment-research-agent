import { mkdir, readFile, writeFile, chmod, access, rename, stat } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash, randomBytes, randomUUID } from 'node:crypto'
import { spawn } from 'node:child_process'
import { installStrategyProfile } from './strategy-profile.js'
import { resolvePython } from '../runtime/python.mjs'
import { npmCommand } from '../runtime/npm.mjs'

export const packageRoot = fileURLToPath(new URL('../../', import.meta.url))
export const profileName = 'huohuo-worker'
export interface Instance {
  version: 1; host: '127.0.0.1'; port: number; principal: string
  user_token: string; worker_token: string; database: string; dsh_home: string
  workspace: string; provider: string; model: string; python: string
}

export async function readInstance(directory: string): Promise<Instance> {
  const value = JSON.parse(await readFile(join(resolve(directory), 'instance.json'), 'utf8'))
  if (value.version !== 1 || value.host !== '127.0.0.1' || !Number.isInteger(value.port)
      || value.port < 1024 || value.port > 65535 || !value.user_token || !value.worker_token) {
    throw new Error('实例配置无效')
  }
  return value
}

export async function createInstanceDirectory(directory: string): Promise<string> {
  const root = resolve(directory)
  await mkdir(dirname(root), { recursive: true, mode: 0o700 })
  // 只递归创建父目录；实例目录仍须原子地新建，禁止复用已有实例。
  await mkdir(root, { mode: 0o700 })
  return root
}

export async function initInstance(directory: string, tarball: string, port = 18386): Promise<void> {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('端口无效：需要 1024～65535 的整数')
  try {
    await stat(resolve(directory))
    throw new Error('实例目录已存在；不会覆盖身份或数据。安装中断请使用 huohuo repair-install <实例目录>。')
  } catch (error: any) { if (error.code !== 'ENOENT') throw error }
  let archive: Buffer
  try {
    if (!tarball) throw new Error('未指定路径')
    archive = await readFile(resolve(tarball))
  } catch { throw new Error('发行包不可读取：请指定现有 tgz 文件后重试；尚未创建实例。') }
  const python = await resolvePython()
  const root = await createInstanceDirectory(directory)
  const pythonRoot = join(root, 'python')
  const instancePython = join(pythonRoot, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  const profile = join(root, 'dsh', 'profiles', profileName)
  await mkdir(profile, { recursive: true, mode: 0o700 })
  await mkdir(join(root, 'workspace'), { mode: 0o700 })
  await writeFile(join(root, 'product.tgz'), archive, { mode: 0o600, flag: 'wx' })
  const config: Instance = {
    version: 1, host: '127.0.0.1', port, principal: randomUUID(),
    user_token: randomBytes(32).toString('base64url'), worker_token: randomBytes(32).toString('base64url'),
    database: join(root, 'business.sqlite3'), dsh_home: join(root, 'dsh'), workspace: join(root, 'workspace'),
    provider: 'deepseek-official', model: 'deepseek-flash', python: instancePython,
  }
  await writeFile(join(root, 'instance.json'), JSON.stringify(config, null, 2) + '\n', { mode: 0o600, flag: 'wx' })
  const state: Initialization = { version: 1, base_python: python.executable,
    package_sha256: createHash('sha256').update(archive).digest('hex'), stage: 'python-environment', status: 'running' }
  await completeInitialization(root, config, state)
  await chmod(join(root, 'instance.json'), 0o600)
}

interface Initialization {
  version: 1; base_python: string; package_sha256: string
  stage: 'python-environment' | 'python-dependencies' | 'worker-dependencies' | 'complete'
  status: 'running' | 'failed' | 'complete'
}

async function saveInitialization(root: string, state: Initialization): Promise<void> {
  const pending = join(root, `initialization.${randomUUID()}.tmp`)
  await writeFile(pending, JSON.stringify(state, null, 2) + '\n', { mode: 0o600 })
  await rename(pending, join(root, 'initialization.json'))
}

async function completeInitialization(root: string, config: Instance, state: Initialization, startAt: Initialization['stage'] = 'python-environment'): Promise<void> {
  const stages = [
    ['python-environment', 'Python 环境', async () => {
      const python = await resolvePython({ explicit: process.env.HUOHUO_PYTHON ?? state.base_python })
      await runProcess(python.executable, ['-m', 'venv', join(root, 'python')], root)
    }],
    ['python-dependencies', 'Python 依赖', () => runProcess(config.python,
      ['-m', 'pip', 'install', '--index-url', process.env.HUOHUO_PIP_INDEX ?? 'https://pypi.org/simple',
        '--retries', '10', '--timeout', '60', '--cache-dir', join(root, 'cache', 'pip'), '-r', join(packageRoot, 'sidecar/requirements.lock')], root)],
    ['worker-dependencies', 'worker 依赖', () => installWorker(config)],
  ] as const
  for (const [stage, label, install] of stages.slice(stages.findIndex(([stage]) => stage === startAt))) {
    state.stage = stage; state.status = 'running'; await saveInitialization(root, state)
    try { await install() }
    catch (cause) {
      state.status = 'failed'; await saveInitialization(root, state)
      throw Object.assign(new Error(`${label}安装失败；已保留实例身份、配置与数据。修复原因后运行 huohuo repair-install ${JSON.stringify(root)}。原因：${cause instanceof Error ? cause.message : '安装未完成'}`, { cause }),
        { exitCode: (cause as { exitCode?: number })?.exitCode })
    }
  }
  state.stage = 'complete'; state.status = 'complete'; await saveInitialization(root, state)
}

export async function repairInstance(directory: string): Promise<void> {
  const root = resolve(directory)
  const config = await readInstance(root)
  let state: Initialization
  try { state = JSON.parse(await readFile(join(root, 'initialization.json'), 'utf8')) }
  catch (error: any) {
    if (error.code === 'ENOENT') {
      // 缺记录也可能是身份已保存、首份日志尚未落盘；必须先核验 Python。
      let pythonAvailable = false
      try { await resolvePython({ explicit: config.python }); pythonAvailable = true } catch {}
      if (pythonAvailable) {
        try {
          await runProcess(config.python, ['-c', 'import importlib.metadata,pathlib,sys\nfor line in pathlib.Path(sys.argv[1]).read_text().splitlines():\n name,expected=line.split("=="); assert importlib.metadata.version(name)==expected, name', join(packageRoot, 'sidecar/requirements.lock')], root)
          await runProcess(config.python, ['-m', 'pip', 'check'], root)
          return installWorker(config)
        } catch (cause: any) { if (cause.exitCode) throw cause }
      }
      const managedPython = join(root, 'python', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
      if (resolve(config.python) !== managedPython) throw new Error('缺少初始化记录且指定 Python 环境不完整；未修改外部环境，请先修复指定 Python 及锁定依赖，再运行 repair-install。')
      const python = await resolvePython()
      state = { version: 1, base_python: python.executable,
        package_sha256: createHash('sha256').update(await readFile(join(root, 'product.tgz'))).digest('hex'),
        stage: pythonAvailable ? 'python-dependencies' : 'python-environment', status: 'running' }
      return completeInitialization(root, config, state, state.stage)
    }
    throw new Error('初始化记录无效；保留原实例，请核对 initialization.json。', { cause: error })
  }
  if (state.version !== 1 || !state.base_python || !state.package_sha256) throw new Error('初始化记录不兼容；未修改实例。')
  const digest = createHash('sha256').update(await readFile(join(root, 'product.tgz'))).digest('hex')
  if (digest !== state.package_sha256) throw new Error('发行包校验值已变化；不能作为中断安装继续，原实例已保留。')
  await completeInitialization(root, config, state)
}

export async function installWorker(config: Instance, refresh = false): Promise<void> {
  const profile = join(config.dsh_home, 'profiles', profileName)
  await access(join(profile, '../../../product.tgz'))
  await mkdir(profile, { recursive: true, mode: 0o700 })
  const manifest = JSON.stringify({
    name: 'huohuo-worker-profile', private: true,
    dependencies: { '@huohuo/research-agent': 'file:../../../product.tgz' },
    dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-sdk-app', '@huohuo/research-agent'] } },
  }, null, 2) + '\n'
  for (const [name, content] of [['package.json', manifest], ['cordis.patch.yml', '[]\n']]) {
    try { await writeFile(join(profile, name), content, { flag: 'wx', mode: 0o600 }) }
    catch (error: any) { if (error.code !== 'EEXIST') throw error }
  }
  const npm = npmCommand()
  await runProcess(npm.command, [...npm.prefix, 'install', ...(refresh ? ['@huohuo/research-agent@file:../../../product.tgz'] : []), '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund', '--prefer-offline', '--cache', join(config.dsh_home, '../cache/npm')], profile)
  await access(join(profile, 'node_modules/@huohuo/research-agent/lib/distribution/cli.js'))
  await access(join(profile, 'node_modules/@deepseek-ai/dsh/lib/bin.js'))
  await installStrategyProfile(config, refresh)
  await writeFile(join(config.dsh_home, '../worker-install.json'), JSON.stringify({ version: '1.0.0', complete: true }), { mode: 0o600 })
}

export async function runProcess(command: string, args: string[], cwd: string): Promise<void> {
  await new Promise<void>((resolvePromise, reject) => {
    const child = spawn(command, args, { cwd, stdio: 'inherit', detached: process.platform !== 'win32' })
    let interrupted = 0
    let timer: ReturnType<typeof setTimeout> | undefined
    const kill = (signal: NodeJS.Signals) => {
      if (!child.pid) return
      try { process.kill(process.platform === 'win32' ? child.pid : -child.pid, signal) } catch {}
    }
    const stop = (signal: NodeJS.Signals) => {
      interrupted = signal === 'SIGINT' ? 130 : 143
      kill('SIGTERM'); timer ??= setTimeout(() => kill('SIGKILL'), 3000)
    }
    const interrupt = () => stop('SIGINT'); const terminate = () => stop('SIGTERM')
    process.on('SIGINT', interrupt); process.on('SIGTERM', terminate)
    const cleanup = () => { clearTimeout(timer); process.off('SIGINT', interrupt); process.off('SIGTERM', terminate) }
    child.once('error', error => { cleanup(); reject(error) })
    child.once('close', (code, signal) => {
      cleanup()
      if (interrupted) reject(Object.assign(new Error('安装已中止；不会继续后续阶段'), { exitCode: interrupted }))
      else if (code === 0) resolvePromise()
      else reject(new Error(`${command} 退出码 ${code ?? signal}`))
    })
  })
}

export class InstanceApiError extends Error {
  constructor(readonly status: number, readonly apiCode: string, readonly detail?: string) {
    super(`实例 API ${status}: ${apiCode}`)
    this.name = 'InstanceApiError'
  }
}

export async function request(config: Instance, path: string, body?: unknown, role: 'user' | 'worker' = 'user', attemptToken?: string, signal?: AbortSignal): Promise<any> {
  const response = await fetch(`http://${config.host}:${config.port}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Authorization: `Bearer ${config[`${role}_token`]}`, 'Content-Type': 'application/json',
      ...(attemptToken ? { 'X-Attempt-Token': attemptToken } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.any([...(signal ? [signal] : []), AbortSignal.timeout((path === '/worker/strategies/tick' || path.endsWith('/strategy-run')) ? 115_000 : path === '/worker/discover' ? 60_000 : 15_000)]),
  })
  const result = await response.json() as any
  if (!response.ok) throw new InstanceApiError(response.status,
    typeof result?.error === 'string' ? result.error : 'unknown_error', typeof result?.detail === 'string' ? result.detail : undefined)
  return result
}

export async function ensureInstalled(config: Instance): Promise<void> {
  const root = resolve(config.dsh_home, '..')
  try {
    let state: Initialization | undefined
    try { state = JSON.parse(await readFile(join(root, 'initialization.json'), 'utf8')) }
    catch (error: any) { if (error.code !== 'ENOENT') throw error }
    if (state && state.status !== 'complete') throw new Error(`初始化阶段 ${state.stage} 尚未完成`)
    const installed = JSON.parse(await readFile(join(root, 'worker-install.json'), 'utf8'))
    if (installed.complete !== true) throw new Error('worker 安装标记未完成')
    const modules = join(config.dsh_home, 'profiles', profileName, 'node_modules')
    await access(join(modules, '@huohuo/research-agent/lib/distribution/cli.js'))
    await access(join(modules, '@deepseek-ai/dsh/lib/bin.js'))
    await access(join(config.dsh_home, 'profiles/huohuo-strategy-worker/node_modules/@huohuo/research-agent/lib/product/strategy-worker.js'))
  } catch (cause) {
    throw new Error(`实例依赖安装未完成；保留原实例，请运行 huohuo repair-install ${JSON.stringify(root)}。`, { cause })
  }
}
