import assert from 'node:assert/strict'
import { spawn, type ChildProcess } from 'node:child_process'
import { appendFile, readFile, writeFile, access } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'
import { createInterface } from 'node:readline/promises'
import { readInstance, request, packageRoot, profileName } from '../distribution/instance.js'
import { workerLoop } from '../distribution/worker.js'

const self = fileURLToPath(import.meta.url)
const mode = process.argv[2]
const observe = process.argv.includes('--observe')
const directory = resolve(process.argv[3] ?? '')
const owner = JSON.parse(await readFile(join(dirname(directory), 'smoke-owner.json'), 'utf8'))
assert.equal(owner.instance, directory, '仅接受本次启动器创建的独立测试实例')
const config = await readInstance(directory)
const abort = new AbortController()
const onStop = () => abort.abort()
process.on('SIGINT', onStop); process.on('SIGTERM', onStop)

if (mode === '--worker') {
  assert.equal(config.provider, 'huohuo-test')
  process.stdin.resume()
  process.stdin.on('end', onStop)
  console.log(JSON.stringify({ event: 'worker-ready', pid: process.pid }))
  try { await workerLoop(config, abort.signal, observe ? observation => console.log(JSON.stringify({ event: 'dsh-observation', observation })) : undefined) }
  finally { process.stdin.destroy() }
} else if (mode === '--run') {
  const interactive = process.argv.includes('--step')
  const terminal = interactive ? createInterface({ input: process.stdin, output: process.stdout }) : undefined
  terminal?.on('SIGINT', onStop)
  const started = new Date().toISOString()
  const cliPath = join(packageRoot, 'lib/distribution/cli.js')
  const logPath = join(owner.reportDir, 'runtime.log')
  const observations: any[] = []
  const demoCases = new Set(['startup', 'create-idempotency', 'research-success', 'cleanup'])
  const cases = [
    ['startup', '正式 serve 入口能启动、停止'],
    ['authentication', '无凭据访问被拒绝'],
    ['create-idempotency', '提交与重复提交不重复建任务'],
    ['research-success', 'DSH 研究完成，独立 CLI 能查询结果与证据'],
    ['tool-boundary', 'Skill 生效且越权工具被拒绝'],
    ['truncated-failure', '模型截断不能冒充成功，也不会自动重跑'],
    ['explicit-retry', '显式重试保留原任务并创建新执行尝试'],
    ['source-failure', '采集失败明确保存为失败'],
    ['queued-cancel', '排队任务取消后不被领取'],
    ['running-cancel', '运行中取消拒绝迟到证据'],
    ['restart', '重启保留记录并继续处理尚未领取的任务'],
    ['cleanup', '停止本次启动的 API 与 worker'],
  ].filter(([id]) => !observe || demoCases.has(id)).map(([id, name]) => ({ id, name, status: 'not-tested' as 'passed' | 'failed' | 'not-tested', detail: '' }))
  type Owned = { child: ChildProcess; finished: Promise<void>; label: string }
  const children = new Set<Owned>()
  let logWrites = Promise.resolve()
  let worker: Owned | undefined
  let api: Owned | undefined
  let success: any
  let retried: any
  let queuedCancel: any
  let runningCancel: any
  const jobs: string[] = []
  let failure: string | undefined
  const redact = (value: string) => value.replaceAll(config.user_token, '[redacted]').replaceAll(config.worker_token, '[redacted]')
  function log(text: string) { logWrites = logWrites.then(() => appendFile(logPath, redact(text))) }

  function showObservation(event: any) {
    observations.push(event)
    if (event.kind === 'runtime.starting') console.log(`\n[DSH] 正在启动 Profile：${event.profile}`)
    else if (event.kind === 'runtime.initialized') {
      const runtime = event.runtime
      console.log(`[DSH] 已完成 SDK 握手；实际版本 ${runtime.dsh_version}，PID ${runtime.pid}`)
      console.log(`[DSH] 实际进程参数：${runtime.argv.map((value: string) => JSON.stringify(value)).join(' ')}`)
      console.log(`[Profile] ${runtime.profile.name}\n[Profile 路径] ${runtime.profile.directory}`)
      console.log(`[已加载 Bundle] ${runtime.profile.started_bundles.join(' → ')}`)
      console.log(`[Skill] huohuo-bounded-quote，SHA256 ${event.skill_sha256}`)
    } else if (event.kind === 'prompt.accepted') console.log(`[DSH 收件] session=${event.session_id}，message=${event.message_id}`)
    else if (event.kind === 'system/message') console.log(`[实际系统提示] 火火 Skill 标识可见：${event.skill_visible}`)
    else if (event.kind === 'request/header') console.log(`[实际模型请求] ${event.provider}/${event.model}（测试模型）；工具：${event.tools.join(', ')}`)
    else if (event.kind === 'tool/call') console.log(`[工具调用] ${event.tool}，call=${event.call_id}`)
    else if (event.kind === 'tool/result') console.log(`[工具返回] is_error=${event.is_error}，证据=${event.evidence_id ?? '无'}，数据状态=${event.evidence_status ?? '无'}`)
    else if (event.kind === 'turn/end') console.log(`[DSH 结束] ${event.reason}`)
    else if (event.kind === 'execution.committed') console.log(`[后台结果入库] ${event.status}`)
    else if (event.kind === 'runtime.closed') console.log('[DSH] 本次运行时已退出')
    else if (event.kind === 'runtime.unsettled') console.log('[DSH] 未确认正常提交；以后台任务状态为准')
  }

  async function launch(label: string, command: string, args: string[], expected: string): Promise<Owned> {
    abort.signal.throwIfAborted()
    const child = spawn(command, args, { cwd: config.workspace, detached: process.platform !== 'win32',
      env: { ...process.env, DEEPSEEK_API_KEY: '', OPENAI_API_KEY: '', ANTHROPIC_API_KEY: '',
        PYTHONPATH: join(packageRoot, 'sidecar'), PYTHONDONTWRITEBYTECODE: '1' }, stdio: ['pipe', 'pipe', 'pipe'] })
    const finished = new Promise<void>(resolveExit => { child.once('close', () => resolveExit()); child.once('error', () => resolveExit()) })
    const owned = { child, finished, label }; children.add(owned)
    await new Promise<void>((ready, reject) => {
      const timeout = setTimeout(() => reject(new Error(`${label} 启动超时`)), 10_000)
      let buffer = ''
      const fail = () => { clearTimeout(timeout); reject(new Error(`${label} 提前退出；详见 runtime.log`)) }
      child.once('exit', fail); child.once('error', fail)
      child.stdout!.on('data', data => {
        log(`[${label}] ${String(data)}`); buffer += String(data)
        let newline: number
        while ((newline = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, newline); buffer = buffer.slice(newline + 1)
          try {
            const value = JSON.parse(line)
            if (observe && value.event === 'dsh-observation') showObservation(value.observation)
            if (value.event === expected || value.status === expected) {
              clearTimeout(timeout); child.off('exit', fail); child.off('error', fail); ready()
            }
          } catch { /* 非协议日志已留存。 */ }
        }
      })
      child.stderr!.on('data', data => log(`[${label}] ${String(data)}`))
    })
    return owned
  }

  async function stop(owned: Owned | undefined): Promise<void> {
    if (!owned || !children.has(owned)) return
    const child = owned.child
    const signal = (value: NodeJS.Signals) => {
      try { if (process.platform !== 'win32' && child.pid) process.kill(-child.pid, value); else child.kill(value) }
      catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error }
    }
    signal('SIGTERM')
    if (child.exitCode === null && child.signalCode === null) {
      const timeout = setTimeout(() => signal('SIGKILL'), 8_000)
      await owned.finished
      clearTimeout(timeout)
    }
    if (process.platform !== 'win32') signal('SIGKILL')
    children.delete(owned)
  }

  async function cli(args: string[], expectedError?: string): Promise<any> {
    abort.signal.throwIfAborted()
    const [command, ...rest] = args
    const result = await new Promise<{ code: number | null; stdout: string; stderr: string }>((resolveRun, reject) => {
      const child = spawn(process.execPath, [cliPath, command, directory, ...rest], { cwd: directory, stdio: ['ignore', 'pipe', 'pipe'] })
      let stdout = ''; let stderr = ''
      const timer = setTimeout(() => child.kill('SIGTERM'), 20_000)
      child.stdout.on('data', value => { stdout += value }); child.stderr.on('data', value => { stderr += value })
      child.once('error', error => { clearTimeout(timer); reject(error) })
      child.once('exit', code => { clearTimeout(timer); resolveRun({ code, stdout, stderr }) })
    })
    log(`[CLI ${args.join(' ')}]\n${result.stdout}${result.stderr}`)
    if (expectedError) {
      assert.equal(result.code, 1)
      assert.ok(result.stderr.includes(expectedError), `期待 ${expectedError}，实际 ${result.stderr}`)
      return
    }
    assert.equal(result.code, 0, result.stderr)
    return JSON.parse(result.stdout)
  }

  async function check(id: string, fn: () => Promise<string>): Promise<void> {
    const item = cases.find(item => item.id === id)
    if (!item) return
    abort.signal.throwIfAborted()
    if (terminal) await terminal.question(`\n按回车开始：${item.name}（Ctrl+C 退出）`, { signal: abort.signal })
    console.log(`开始：${item.name}`)
    try { item.detail = await fn(); item.status = 'passed'; console.log(`  PASS  ${item.detail}`) }
    catch (error) {
      item.status = 'failed'; item.detail = redact(error instanceof Error ? error.message : String(error))
      console.error(`  FAIL  ${item.detail}`); throw error
    }
  }

  async function source(value: 'ok' | 'error' | 'hold') {
    await writeFile(join(directory, 'fixture.json'), JSON.stringify({ mode: value }))
  }
  async function model(value: string) {
    config.model = value
    await writeFile(join(directory, 'instance.json'), JSON.stringify(config), { mode: 0o600 })
  }
  async function startWorker() { worker = await launch('worker', process.execPath, [self, '--worker', directory, ...(observe ? ['--observe'] : [])], 'worker-ready') }
  async function startApi() { api = await launch('API', config.python, [join(packageRoot, 'tests/fixtures/smoke_server.py'), directory], 'listening') }
  async function submit(label: string) {
    const path = join(directory, label + '.json')
    const body = { request_key: label, scope: { entity_id: 'SEC:CN:A:600519', exchange: 'SSE', operation: 'quote_snapshot' }, question: '请解释本次合成冒烟快照及数据限制。' }
    await writeFile(path, JSON.stringify(body))
    const result = await cli(['submit', path]); jobs.push(result.execution_id)
    return { path, body, result }
  }
  async function until(id: string, status: string) {
    const deadline = Date.now() + 60_000
    while (Date.now() < deadline) {
      abort.signal.throwIfAborted()
      const value = await cli(['get', id])
      if (value.status === status) return value
      assert.ok(['queued', 'running'].includes(value.status), `期待 ${status}，实际 ${value.status}: ${JSON.stringify(value.result)}`)
      if (worker && (worker.child.exitCode !== null || worker.child.signalCode !== null)) throw new Error('worker 提前退出')
      await delay(200, undefined, { signal: abort.signal })
    }
    throw new Error(`执行 ${id} 未在 60 秒内进入 ${status}`)
  }
  async function events(id: string) { return await cli(['events', id]) as any[] }
  async function waitForFile(path: string) {
    const end = Date.now() + 30_000
    while (Date.now() < end) {
      try { await access(path); return } catch { await delay(100, undefined, { signal: abort.signal }) }
    }
    throw new Error(`等待测试闸门超时：${path}`)
  }

  try {
    config.provider = 'huohuo-test'
    await model(observe ? 'demo-fixture' : 'fixture'); await source('ok')
    await writeFile(join(config.dsh_home, 'profiles', profileName, 'cordis.patch.yml'), `
- id: llm-deepseek
  disabled: true
- id: llm-deepseek-account
  disabled: true
- id: llm-pi-ai
  disabled: true
- insert:
    - id: huohuo-test-model
      name: '${join(packageRoot, 'lib/tests/test-model.js')}'
`)
    console.log(`验收范围：${observe ? 'DSH Profile 的单次实际装配与执行' : '后台结构冒烟'}。模型=确定性测试适配器；行情=合成样本。\n`)
    if (observe) console.log(`实例目录：${directory}\n下面内容来自运行时回执及 SDK 事件；此入口是 SDK 后台执行，不是 DSH 聊天 TUI。\n`)
    await check('startup', async () => {
      const actual = await launch('正式 serve', process.execPath, [cliPath, 'serve', directory], 'ready')
      assert.equal((await request(config, '/health')).version, '1.0.0')
      await stop(actual)
      await startApi()
      return '正式入口已就绪并退出；后续业务场景使用注入合成数据的真实 API＋worker。'
    })
    await check('authentication', async () => {
      const response = await fetch(`http://127.0.0.1:${config.port}/health`, { signal: AbortSignal.timeout(3_000) })
      assert.equal(response.status, 403)
      return '未携带实例凭据的请求返回 403。'
    })
    let input: Awaited<ReturnType<typeof submit>>
    await check('create-idempotency', async () => {
      input = await submit('smoke-create')
      assert.equal(input.result.status, 'queued')
      const again = await cli(['submit', input.path])
      assert.equal(again.execution_id, input.result.execution_id)
      const conflicting = join(directory, 'conflicting.json')
      await writeFile(conflicting, JSON.stringify({ ...input.body, question: '同键但不同请求' }))
      await cli(['submit', conflicting], '409')
      assert.equal((await events(again.execution_id)).filter(event => event.kind === 'execution.created').length, 1)
      return `任务 ${again.execution_id}；重复提交仍是同一任务，改内容返回 409。`
    })
    await check('research-success', async () => {
      await startWorker()
      success = await until(input!.result.execution_id, 'succeeded')
      assert.equal(success.result.execution_id, success.execution_id)
      assert.deepEqual(success.result.scope, input!.body.scope)
      const evidence = await cli(['evidence', success.execution_id])
      assert.ok(success.result.evidence_ids.length > 0)
      for (const id of success.result.evidence_ids) {
        const record = evidence.find((item: any) => item.evidence_id === id)
        assert.equal(record.attempt_id, success.current_attempt); assert.equal(record.status, 'ok')
        assert.equal(record.values.price, '12.1'); assert.equal(record.values.change_percent, '21.0000')
        assert.ok(record.source_url.startsWith('https://example.invalid/'))
      }
      const history = await events(success.execution_id)
      assert.equal(history.filter(item => item.kind === 'attempt.claimed').length, 1)
      assert.equal(history.filter(item => item.kind === 'runtime.accepted').length, 1)
      assert.equal(history.filter(item => item.kind === 'execution.succeeded').length, 1)
      if (observe) {
        for (let i = 0; i < 50 && !observations.some(item => item.kind === 'execution.committed'); i++) await delay(100, undefined, { signal: abort.signal })
        const initialized = observations.find(item => item.kind === 'runtime.initialized')
        assert.equal(initialized.runtime.profile.name, profileName)
        assert.equal(initialized.runtime.dsh_version, '0.2.1-rc.2')
        assert.ok(initialized.runtime.pid > 0)
        assert.deepEqual(initialized.runtime.argv.slice(-2), ['--profile', profileName])
        assert.deepEqual(initialized.runtime.profile.started_bundles, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-sdk-app', '@huohuo/research-agent'])
        assert.ok(observations.some(item => item.kind === 'system/message' && item.skill_visible === true))
        assert.ok(observations.some(item => item.kind === 'request/header' && item.tools.length === 1 && item.tools[0] === 'read_security_snapshot'))
        assert.ok(observations.some(item => item.kind === 'tool/call' && item.tool === 'read_security_snapshot'))
        assert.ok(observations.some(item => item.kind === 'tool/result' && success.result.evidence_ids.includes(item.evidence_id) && !item.is_error))
        assert.ok(observations.some(item => item.kind === 'turn/end' && item.reason === 'completed'))
        assert.ok(observations.some(item => item.kind === 'execution.committed' && item.status === 'succeeded'))
        console.log(`[任务] ${success.execution_id}\n[实际结果] ${success.result.summary}`)
        console.log(`[运行时装配回执] ${join(directory, 'runs', success.current_attempt, 'assembly.json')}`)
      }
      return '提交客户端已经退出；后台完成研究，证据属于本次执行；合成价格 12.1、变化 21.0000%。'
    })
    await check('tool-boundary', async () => {
      const proof = JSON.parse(await readFile(join(directory, 'runs', success.current_attempt, 'test-proof.json'), 'utf8'))
      assert.equal(proof.skill_loaded, true); assert.equal(proof.root_guard, true); assert.equal(proof.agent_scope_guard, true)
      assert.deepEqual(proof.tool_names, ['read_security_snapshot'])
      assert.deepEqual(proof.blocked_calls, ['bash', 'write', 'web_fetch', 'subagent', 'run_code'])
      return '实际 Agent 仅见报价工具；5 类越权调用及根级/Agent 哨兵均被拒绝。'
    })
    let failed: any
    await check('truncated-failure', async () => {
      await stop(worker); worker = undefined
      await model('truncated-fixture'); await startWorker()
      const submitted = await submit('smoke-truncated')
      failed = await until(submitted.result.execution_id, 'failed')
      assert.match(failed.result.error, /max-tokens/)
      assert.equal((await cli(['evidence', failed.execution_id]))[0].status, 'ok')
      await delay(1_200, undefined, { signal: abort.signal })
      assert.equal((await cli(['get', failed.execution_id])).status, 'failed')
      assert.equal((await events(failed.execution_id)).filter(event => event.kind === 'attempt.claimed').length, 1)
      return `任务 ${failed.execution_id}：有真实工具证据和合法成功 JSON，仍因模型截断标记 failed；无自动重跑。`
    })
    await check('explicit-retry', async () => {
      await stop(worker); worker = undefined
      await model('fixture')
      const args = ['retry', failed.execution_id, String(failed.revision), 'smoke-retry']
      const receipt = await cli(args)
      assert.equal(receipt.status, 'queued'); assert.equal(receipt.execution_id, failed.execution_id)
      assert.deepEqual(await cli(args), receipt)
      await startWorker()
      retried = await until(failed.execution_id, 'succeeded')
      assert.notEqual(retried.current_attempt, failed.current_attempt)
      assert.deepEqual(await cli(args), receipt)
      const evidence = await cli(['evidence', retried.execution_id])
      assert.ok(evidence.some((item: any) => item.attempt_id === failed.current_attempt && item.attempt_status === 'failed'))
      assert.ok(evidence.some((item: any) => item.attempt_id === retried.current_attempt && item.attempt_status === 'succeeded'))
      assert.equal((await events(retried.execution_id)).filter(event => event.kind === 'attempt.claimed').length, 2)
      return `同一任务重试成功；旧尝试 ${failed.current_attempt} 保留，新尝试 ${retried.current_attempt}。`
    })
    await check('source-failure', async () => {
      await source('error')
      const submitted = await submit('smoke-source-error')
      const result = await until(submitted.result.execution_id, 'failed')
      const evidence = await cli(['evidence', result.execution_id])
      assert.equal(evidence[0].status, 'error'); assert.equal(evidence[0].error_type, 'TimeoutError')
      assert.match(result.result.error, /没有取得可用证据/)
      await source('ok')
      return '注入采集超时，结果严格为 failed，证据明确为 error。'
    })
    await check('queued-cancel', async () => {
      await stop(worker); worker = undefined
      const submitted = await submit('smoke-queued-cancel')
      queuedCancel = await cli(['cancel', submitted.result.execution_id, String(submitted.result.revision), 'cancel-queued'])
      assert.equal(queuedCancel.status, 'cancelled')
      await startWorker(); await delay(600, undefined, { signal: abort.signal })
      assert.equal((await events(queuedCancel.execution_id)).filter(event => event.kind === 'attempt.claimed').length, 0)
      return `排队任务 ${queuedCancel.execution_id} 已取消，未产生领取记录。`
    })
    await check('running-cancel', async () => {
      await source('hold')
      const submitted = await submit('smoke-running-cancel')
      await waitForFile(join(directory, 'tool-entered'))
      const running = await cli(['get', submitted.result.execution_id])
      assert.equal(running.status, 'running')
      try {
        runningCancel = await cli(['cancel', running.execution_id, String(running.revision), 'cancel-running'])
        assert.equal(runningCancel.status, 'cancelled')
      } finally { await writeFile(join(directory, 'tool-release'), 'release') }
      const end = Date.now() + 10_000
      let rejected = false
      while (Date.now() < end) {
        const lines = (await readFile(join(directory, 'evidence-outcomes.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line))
        const outcome = lines.find(item => item.attempt_id === running.current_attempt)
        if (outcome) {
          assert.equal(outcome.outcome, 'rejected', '迟到写入必须是契约拒绝，不能是存储或程序异常')
          assert.equal(outcome.reason, 'execution capability expired or revoked')
          rejected = true
        }
        if (rejected) break
        await delay(100, undefined, { signal: abort.signal })
      }
      assert.equal(rejected, true, '取消后迟到证据必须由真实 Repository 拒绝')
      assert.deepEqual(await cli(['evidence', running.execution_id]), [])
      assert.equal((await cli(['get', running.execution_id])).status, 'cancelled')
      assert.equal((await events(running.execution_id)).filter(event => event.kind === 'execution.succeeded').length, 0)
      assert.equal((await cli(['get', queuedCancel.execution_id])).status, 'cancelled')
      assert.equal((await events(queuedCancel.execution_id)).filter(event => event.kind === 'attempt.claimed').length, 0)
      await source('ok')
      return `运行中的任务 ${running.execution_id} 已取消；释放数据闸门后，迟到证据被实际数据库契约拒绝。`
    })
    await check('restart', async () => {
      await stop(worker); worker = undefined
      const pending = await submit('smoke-queued-before-restart')
      assert.equal(pending.result.status, 'queued')
      const before = new Map<string, any>()
      for (const id of jobs) before.set(id, { job: await cli(['get', id]), events: await events(id), evidence: await cli(['evidence', id]) })
      await stop(api); api = undefined
      await startApi()
      for (const id of jobs) {
        assert.deepEqual(await cli(['get', id]), before.get(id).job)
        assert.deepEqual(await events(id), before.get(id).events)
        assert.deepEqual(await cli(['evidence', id]), before.get(id).evidence)
      }
      await startWorker()
      await until(pending.result.execution_id, 'succeeded')
      for (const id of jobs.filter(id => id !== pending.result.execution_id)) assert.deepEqual(await cli(['get', id]), before.get(id).job)
      return '成功、失败、取消、历史证据和排队记录均保留；只处理原先未领取的任务，终态不重跑。'
    })
    const records = []
    for (const id of jobs) records.push({ execution: await cli(['get', id]), events: await events(id), evidence: await cli(['evidence', id]) })
    await writeFile(join(owner.reportDir, 'execution-records.json'), JSON.stringify(records, null, 2))
  } catch (error) {
    failure = redact(error instanceof Error ? error.message : String(error))
    process.exitCode = abort.signal.aborted ? 130 : 1
  } finally {
    terminal?.close()
    const cleanup = cases.find(item => item.id === 'cleanup')!
    try {
      for (const child of [...children]) await stop(child)
      cleanup.status = 'passed'; cleanup.detail = '本次启动的直接子进程 API、worker 与 serve 均已退出。'
    } catch (error) {
      cleanup.status = 'failed'; cleanup.detail = String(error); process.exitCode = 1
      failure ??= cleanup.detail
    }
    await logWrites
    if (observe) await writeFile(join(owner.reportDir, 'dsh-events.jsonl'), observations.map(item => JSON.stringify(item)).join('\n') + '\n')
    const passed = !abort.signal.aborted && cases.every(item => item.status === 'passed')
    const status = abort.signal.aborted ? 'aborted' : passed ? 'passed' : 'failed'
    process.exitCode = status === 'aborted' ? 130 : passed ? 0 : 1
    const report = { version: '1.0.0', suite: observe ? 'dsh-profile-demo' : 'backend-smoke', status,
      product_acceptance: 'not-tested', started_at: started, finished_at: new Date().toISOString(),
      mode: observe ? 'observe' : interactive ? 'step' : 'automatic', model: 'deterministic fixture', data: 'synthetic fixture',
      source_code: 'installed tarball', package_integrity: owner.integrity, instance: directory, cases, failure: failure ?? null }
    await writeFile(join(owner.reportDir, 'report.json'), JSON.stringify(report, null, 2))
    const lines = cases.map(item => `| ${item.name} | ${item.status} | ${item.detail.replaceAll('|', '\\|').replaceAll('\n', ' ')} |`)
    await writeFile(join(owner.reportDir, 'report.md'), `# 火火 1.0.0 ${observe ? 'DSH Profile 单次执行演示' : '后台冒烟'}\n\n结果：**${report.status}**。运行时间：${started}。\n\n本次为确定性测试模型＋合成行情；实际运行 CLI、DSH Profile/Bundle/Skill、工具、Python API、SQLite。真实模型质量、真实行情可用性、持续委托核心及 UI 均为 not-tested。\n\n| 检查 | 状态 | 观察结果 |\n|---|---|---|\n${lines.join('\n')}\n\n${failure ? '失败原因：' + failure + '\n\n' : ''}执行记录：[execution-records.json](execution-records.json)。日志：[runtime.log](runtime.log)。${observe ? 'DSH 事件：[dsh-events.jsonl](dsh-events.jsonl)。' : ''}\n\n实例：${directory}。发行包完整性：${owner.integrity}。\n`)
    console.log(`\n${observe ? 'DSH Profile 演示' : '后台冒烟'} ${status === 'aborted' ? 'ABORTED' : passed ? 'PASS' : 'FAIL'}：${cases.filter(item => item.status === 'passed').length}/${cases.length} 项通过。`)
    console.log('这不等于真实模型投研、真实行情或完整 1.0.0 验收通过。')
  }
} else { throw new Error('请从 npm run smoke 启动') }
process.off('SIGINT', onStop); process.off('SIGTERM', onStop)
