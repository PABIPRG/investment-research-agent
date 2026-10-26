import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { mkdir, mkdtemp, realpath, writeFile, appendFile, access, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'
import { randomUUID } from 'node:crypto'
import { smokeFingerprint, archiveIntegrity, validateSmokeResume } from './smoke-provenance.mjs'
import { resolvePython } from '../runtime/python.mjs'

const root = fileURLToPath(new URL('../', import.meta.url))
const args = process.argv.slice(2)
const installTimeout = Number(process.env.HUOHUO_SMOKE_INSTALL_TIMEOUT_MS ?? 900000)
if (!Number.isInteger(installTimeout) || installTimeout < 1000 || installTimeout > 3600000) throw new Error('安装超时须为 1000–3600000 毫秒')
const port = Number(process.env.HUOHUO_SMOKE_PORT ?? 18810)
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('HUOHUO_SMOKE_PORT 须为 1024–65535')
if (args.some(arg => !['--step', '--observe'].includes(arg))) throw new Error('支持：npm run smoke、npm run smoke -- --step 或 npm run dsh:demo')
if (args.includes('--step') && !process.stdin.isTTY) throw new Error('逐步模式需要交互式终端；自动执行请去掉 --step')
const id = new Date().toISOString().replace(/[:.]/g, '-') + '-' + randomUUID().slice(0, 8)
const tempBase = process.env.HUOHUO_SMOKE_TMP ?? tmpdir()
await mkdir(tempBase, { recursive: true, mode: 0o700 })
const reportDir = join(root, 'artifacts', 'smoke', id)
await mkdir(reportDir, { recursive: true, mode: 0o700 })
const logPath = join(reportDir, 'bootstrap.log')
let active
let interrupted = false
let logWrites = Promise.resolve()
let pythonPath
const abort = () => { interrupted = true; active?.() }
process.on('SIGINT', abort); process.on('SIGTERM', abort)

async function run(command, argv, options = {}) {
  if (interrupted) throw new Error('用户中止冒烟')
  await appendFile(logPath, `\n[${new Date().toISOString()}] ${command} ${argv.join(' ')}\n`)
  if (interrupted) throw new Error('用户中止冒烟')
  return await new Promise((resolveRun, reject) => {
    // 非交互安装使用独立进程组，中止 init 时也能回收它创建的 npm。
    const grouped = process.platform !== 'win32' && !options.live
    const child = spawn(command, argv, { cwd: root, env: { ...process.env, ...(pythonPath ? { HUOHUO_PYTHON: pythonPath } : {}), npm_config_prefer_offline: 'true', DEEPSEEK_API_KEY: '', OPENAI_API_KEY: '', ANTHROPIC_API_KEY: '' },
      detached: grouped, stdio: options.live ? 'inherit' : ['ignore', 'pipe', 'pipe'] })
    let stdout = ''
    let stopping = false
    let killTimer
    const signal = value => {
      try { if (grouped && child.pid) process.kill(-child.pid, value); else child.kill(value) }
      catch (error) { if (error.code !== 'ESRCH') throw error }
    }
    const terminate = () => {
      if (stopping) return
      stopping = true; signal('SIGTERM')
      killTimer = setTimeout(() => signal('SIGKILL'), options.live ? 25_000 : 8_000)
    }
    active = terminate
    const timer = setTimeout(terminate, options.timeout ?? 300_000)
    const record = chunk => { logWrites = logWrites.then(() => appendFile(logPath, chunk)) }
    child.stdout?.on('data', chunk => { stdout += chunk; record(chunk) })
    child.stderr?.on('data', record)
    child.once('error', error => { clearTimeout(timer); clearTimeout(killTimer); active = undefined; reject(error) })
    child.once('close', (code, exitSignal) => {
      clearTimeout(timer); clearTimeout(killTimer); active = undefined
      if (stopping && grouped) signal('SIGKILL')
      if (code === 0 && !interrupted && !stopping) resolveRun(stdout)
      else if (code === 130) { interrupted = true; reject(new Error('用户中止冒烟')) }
      else reject(new Error(`${command} 未完成（退出码 ${code}，信号 ${exitSignal ?? '无'}）；详见 ${logPath}`))
    })
  })
}

let testRoot
let phase = '环境检查'
try {
  console.log(`火火 1.0.0 ${args.includes('--observe') ? 'DSH Profile 单次执行演示' : '后台冒烟'}：测试模型＋合成行情，不调用真实模型，不访问行情源。`)
  console.log('检查真实 CLI、DSH、工具、Python API 与 SQLite；不代表完整产品验收。')
  console.log(`报告目录：${reportDir}\n`)
  const [major, minor] = process.versions.node.split('.').map(Number)
  if (major < 24 || (major === 24 && minor < 8)) throw new Error('需要 Node.js 24.8 或以上版本')
  const python = await resolvePython()
  pythonPath = python.executable
  for (const checked of python.checked) console.log(`跳过解释器：${checked}`)
  console.log(`使用 Python ${python.version}：${python.executable}`)
  await appendFile(logPath, JSON.stringify({ python }) + '\n')
  await new Promise((resolvePort, reject) => {
    const server = createServer()
    server.once('error', () => reject(new Error(`本地 ${port} 端口已占用；请为 HUOHUO_SMOKE_PORT 选择空闲端口。脚本不会终止其他服务。`)))
    server.listen(port, '127.0.0.1', () => server.close(resolvePort))
  })
  try { await access(join(root, 'node_modules', '.bin', 'tsc')) }
  catch { console.log('准备构建依赖（首次需要访问 npm）…'); await run('npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund']) }
  phase = '构建与打包'
  console.log('准备 1/3：构建当前代码并生成独立发行包…')
  await run('npm', ['run', 'build'])
  const runtimeFingerprint = await smokeFingerprint(root)
  const resume = process.env.HUOHUO_SMOKE_RESUME
  testRoot = resume ? await realpath(resume) : await realpath(await mkdtemp(join(tempBase, 'huohuo-smoke-')))
  let packed
  if (resume) {
    const previous = JSON.parse(await readFile(join(testRoot, 'smoke-owner.json'), 'utf8'))
    validateSmokeResume(previous, join(testRoot, 'instance'), runtimeFingerprint, await archiveIntegrity(join(testRoot, 'instance/product.tgz')))
    packed = { integrity: previous.integrity }
  } else packed = JSON.parse(await run('npm', ['pack', '--json', '--pack-destination', testRoot]))[0]
  const instance = join(testRoot, 'instance')
  await writeFile(join(testRoot, 'smoke-owner.json'), JSON.stringify({ id, instance, reportDir, integrity: packed.integrity, runtime_fingerprint: runtimeFingerprint }), { mode: 0o600 })
  phase = '全新实例安装'
  console.log('准备 2/3：安装到全新测试实例（首次安装可能需要几分钟）…')
  if (resume) {
    const config = JSON.parse(await readFile(join(instance, 'instance.json'), 'utf8'))
    if (config.port !== port) throw new Error('恢复端口须与原冒烟实例一致')
    await run(process.execPath, [join(root, 'lib/distribution/cli.js'), 'repair-install', instance], { timeout: installTimeout })
  } else await run(process.execPath, [join(root, 'lib/distribution/cli.js'), 'init', instance, join(testRoot, packed.filename), String(port)], { timeout: installTimeout })
  phase = '运行冒烟'
  console.log('准备 3/3：启动实际后台验收…\n')
  const suite = join(root, 'lib/tests/smoke.js')
  await run(process.execPath, [suite, '--run', instance, ...args], { live: true, timeout: args.includes('--step') ? 43_200_000 : 300_000 })
} catch (error) {
  process.exitCode = interrupted ? 130 : 1
  const detail = error instanceof Error ? error.message : String(error)
  console.error(`\n冒烟未通过：${phase}；${detail}`)
  try { await access(join(reportDir, 'report.json')) }
  catch {
    await writeFile(join(reportDir, 'report.json'), JSON.stringify({ status: interrupted ? 'aborted' : 'failed', phase, detail, model: 'deterministic fixture', data: 'synthetic fixture', testRoot }, null, 2))
    await writeFile(join(reportDir, 'report.md'), `# 后台冒烟未通过\n\n阶段：${phase}。\n\n${detail}\n\n后续业务步骤：not-tested。日志：${logPath}\n`)
  }
} finally {
  await logWrites
  process.off('SIGINT', abort); process.off('SIGTERM', abort)
  console.log(`\n查看报告：${join(reportDir, 'report.md')}`)
  console.log(`机器可读结果：${join(reportDir, 'report.json')}`)
}
