// 真实 DSH Profile / Bundle / SDK / HTTP / SQLite；模型和事件均为合成数据。
// 不运行 npm 安装、不修改共享 node_modules、不读取已有实例或模型凭据。
import assert from 'node:assert/strict'
import { access, mkdir, mkdtemp, readFile, writeFile, readdir, symlink, copyFile } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomBytes, randomUUID, createHash } from 'node:crypto'

const root = fileURLToPath(new URL('../', import.meta.url))
const runtime = resolve(process.env.HUOHUO_STRATEGY_RUNTIME_ROOT ?? root)
const python = process.env.HUOHUO_PYTHON
assert.ok(python, '请显式提供 HUOHUO_PYTHON，不能自动复用用户实例')
const port = Number(process.env.HUOHUO_STRATEGY_SMOKE_PORT ?? 18852)
assert.ok(Number.isInteger(port) && port >= 1024 && port <= 65535)
const runtimeFile = join(runtime, 'lib/distribution/strategy-worker.js')
const modelFile = join(root, 'lib/tests/strategy-runtime-model.js')
await Promise.all([access(runtimeFile), access(modelFile), access(python)])
const { runStrategyPlanner } = await import(pathToFileURL(runtimeFile).href)
const { request } = await import(pathToFileURL(join(runtime, 'lib/distribution/instance.js')).href)
const output = join(root, 'artifacts/strategy-runtime-smoke')
await mkdir(output, { recursive: true, mode: 0o700 })
const instance = await mkdtemp(join(output, 'instance-'))
const proof = join(instance, 'model-proof.jsonl')
const config = { version: 1, host: '127.0.0.1', port, principal: randomUUID(),
  user_token: randomBytes(32).toString('base64url'), worker_token: randomBytes(32).toString('base64url'),
  database: join(instance, 'business.sqlite'), dsh_home: join(instance, 'dsh'),
  workspace: join(instance, 'workspace'), provider: 'huohuo-strategy-fixture', model: 'controlled', python }
await mkdir(config.workspace, { recursive: true, mode: 0o700 })
await writeFile(join(instance, 'instance.json'), JSON.stringify(config), { mode: 0o600 })
await mkdir(join(instance, 'home'), { mode: 0o700 }); await mkdir(join(instance, 'tmp'), { mode: 0o700 })
// runStrategyPlanner 只挑选环境白名单；将其中的用户目录、代理与凭据显式隔离。
process.env.HOME = join(instance, 'home'); process.env.TMPDIR = join(instance, 'tmp')
for (const key of ['DEEPSEEK_API_KEY', 'HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy']) delete process.env[key]
process.env.NO_PROXY = '127.0.0.1,localhost'
const profile = join(config.dsh_home, 'profiles/huohuo-strategy-worker')
const modules = join(profile, 'node_modules')
await mkdir(join(modules, '@huohuo'), { recursive: true, mode: 0o700 })
// 只在独立实例建立依赖链接；包中的相对解析仍从只读的编译候选完成。
for (const entry of await readdir(join(runtime, 'node_modules'))) {
  if (entry !== '@huohuo') await symlink(join(runtime, 'node_modules', entry), join(modules, entry), 'dir')
}
await symlink(runtime, join(modules, '@huohuo/research-agent'), 'dir')
const bundle = join(profile, 'strategy-bundle')
await mkdir(bundle, { mode: 0o700 })
await writeFile(join(bundle, 'package.json'), JSON.stringify({ name: '@huohuo/strategy-bundle', version: '1.0.0',
  private: true, engines: { dsh: '0.2.1-rc.2' }, dsh: { bundle: { patch: './cordis.patch.yml' } } }))
await copyFile(join(runtime, 'product/profile/huohuo-strategy-worker.yml'), join(bundle, 'cordis.patch.yml'))
await symlink(bundle, join(modules, '@huohuo/strategy-bundle'), 'dir')
const bundles = ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-sdk-app', '@huohuo/strategy-bundle']
await writeFile(join(profile, 'package.json'), JSON.stringify({ name: 'huohuo-strategy-smoke-profile', private: true,
  dsh: { profile: { bundles } } }), { mode: 0o600 })
await writeFile(join(profile, 'cordis.patch.yml'), `- id: llm-deepseek\n  disabled: true\n- id: llm-deepseek-account\n  disabled: true\n- id: llm-pi-ai\n  disabled: true\n- insert:\n    - id: strategy-runtime-model\n      name: ${JSON.stringify(modelFile)}\n      config:\n        proofPath: ${JSON.stringify(proof)}\n`, { mode: 0o600 })
const controller = new AbortController()
let api, apiLog = '', report = { status: 'running', synthetic_model: true, synthetic_events: true,
  assembly: 'source-linked real DSH profile/bundle', runtime_root: runtime, instance, port, checks: [] }
const check = (name, detail) => report.checks.push({ name, status: 'passed', detail })
function stopSignal() { controller.abort(); api?.stdin.end() }
process.on('SIGINT', stopSignal); process.on('SIGTERM', stopSignal)
async function stop() {
  if (!api || api.exitCode !== null || api.signalCode !== null) return
  const exited = new Promise((r) => api.once('exit', r))
  api.stdin.end()
  const timer = setTimeout(() => api.kill('SIGKILL'), 5000)
  await exited; clearTimeout(timer)
}
async function start() {
  api = spawn(python, ['-m', 'huohuo.server', '--config', join(instance, 'instance.json'), '--parent-pipe'], {
    cwd: runtime, env: { PATH: process.env.PATH, HOME: process.env.HOME, TMPDIR: process.env.TMPDIR,
      LANG: 'en_US.UTF-8', PYTHONPATH: join(runtime, 'sidecar'), PYTHONDONTWRITEBYTECODE: '1' },
    stdio: ['pipe', 'pipe', 'pipe'],
  })
  api.stderr.on('data', (x) => { apiLog += String(x) })
  await new Promise((yes, no) => {
    const timer = setTimeout(() => no(Error('侧车启动超时')), 15000)
    api.stdout.once('data', () => { clearTimeout(timer); yes() })
    api.once('error', (e) => { clearTimeout(timer); no(e) })
    api.once('exit', (code) => { clearTimeout(timer); no(Error('侧车退出 ' + code + ': ' + apiLog.slice(-1500))) })
  })
}
async function command(action, payload) {
  const request_key = randomUUID(), session_id = 'synthetic-strategy-runtime-smoke'
  const preview = await request(config, '/strategies/prepare', { session_id, request_key, action, payload })
  const result = await request(config, '/strategies/commit', { session_id, request_key, preview_id: preview.preview_id })
  assert.equal(result.run.status, 'completed', JSON.stringify(result))
  return result
}
async function plan() {
  const current = (await request(config, '/strategies')).automation
  return Object.fromEntries(['revision', 'enabled', 'daily_time', 'strategy_ids', 'actions', 'retest_days',
    'lookback_days', 'event_candidates', 'archive_recall'].map((key) => [key, current[key]]))
}
async function modelRun(title) {
  const event = { id: randomUUID(), source: 'synthetic:strategy-runtime-smoke', observed_at: Date.now() / 1000,
    title, summary: '合成新闻，仅验证程序链路，不是真实来源或投资判断',
    securities: [{ code: '600519', name: '贵州茅台' }], evidence_ref: 'synthetic:runtime-smoke' }
  const ingest = await request(config, '/worker/strategies/events', { events: [event] }, 'worker')
  assert.equal(ingest.queued.length, 1)
  const job = await request(config, '/worker/claim', { worker_id: 'synthetic-runtime-worker', lane: 'strategy', admission_policy: 'hook-model-gate-v1' }, 'worker')
  assert.equal(job.job_id, ingest.queued[0])
  assert.ok(job.execution_id && job.attempt_id, '候选必须绑定统一 execution/attempt')
  assert.equal(await runStrategyPlanner(config, job, controller.signal), 'completed', '真实 DSH 应完成并交回候选')
  const acks = (await readdir(join(instance, 'strategy-runs', job.job_id))).filter((x) => x.startsWith('assembly-'))
  assert.equal(acks.length, 1)
  const ack = JSON.parse(await readFile(join(instance, 'strategy-runs', job.job_id, acks[0]), 'utf8'))
  assert.equal(ack.runtime.profile.name, 'huohuo-strategy-worker'); assert.deepEqual(ack.tools, [])
  assert.ok(JSON.stringify(ack.runtime.profile.started_bundles).includes('@huohuo/strategy-bundle'))
  assert.ok(!JSON.stringify(ack.runtime.profile.started_bundles).includes('@huohuo/research-agent'))
  return job.job_id
}
try {
  await new Promise((yes, no) => { const s = createServer(); s.once('error', no); s.listen(port, '127.0.0.1', () => s.close(yes)) })
  await start()
  const seed = await command('create', { name: '合成范围策略', kind: 'momentum', params: { n: 5 },
    securities: [{ code: '600519', name: '贵州茅台' }], direction: '其他', rationale: '仅供隔离装配验收' })
  await command('schedule', { ...await plan(), enabled: true, event_candidates: true, strategy_ids: [seed.strategy.id] })
  check('confirmed-scope', '临时实例通过真实预览/确认接口保存范围，未触发外部来源采集')
  await assert.rejects(request(config, '/worker/claim', { worker_id: 'user', lane: 'strategy' }), (e) => e.status === 403)
  await assert.rejects(request(config, '/strategies/prepare', {}, 'worker'), (e) => e.status === 403)
  check('credential-boundary', '用户凭据不能领取 worker 任务，worker 凭据不能写正式策略')
  const first = await modelRun('合成正常候选验证')
  let view = await request(config, '/strategies')
  assert.equal(view.suggestions.length, 1); assert.equal(view.strategies.length, 1)
  assert.equal(view.planner_jobs.find((x) => x.id === first).status, 'completed')
  check('candidate-staging', '统一 claim 领取 execution/attempt；真实 DSH 模型输出经侧车校验，仅生成待确认建议，正式策略数不变')
  await modelRun('合成禁止写入验证')
  view = await request(config, '/strategies')
  assert.equal(view.strategies.length, 1); assert.equal(view.suggestions.length, 1)
  const samples = (await readFile(proof, 'utf8')).trim().split('\n').map(JSON.parse)
  assert.ok(samples.every((x) => x.tools.length === 0))
  assert.ok(samples.some((x) => x.scenario === 'forbidden-write' && x.rejected))
  check('model-write-denied', '模型故意调用 commit_strategy 被真实 DSH 拒绝，工具目录始终为空')
  const suggestion = view.suggestions[0]
  await stop(); await start()
  view = await request(config, '/strategies')
  assert.equal(view.suggestions[0].id, suggestion.id); assert.equal(view.strategies.length, 1)
  assert.equal(await request(config, '/worker/claim', { worker_id: 'restart', lane: 'strategy', admission_policy: 'hook-model-gate-v1' }, 'worker'), null)
  check('restart-persistence', '重启侧车后候选仍在，已完成任务不重放，正式策略不新增')
  await command('accept_suggestion', { suggestion_id: suggestion.id })
  view = await request(config, '/strategies')
  assert.equal(view.strategies.length, 2)
  assert.equal(view.suggestions.filter((x) => x.status === 'pending').length, 0)
  assert.equal(view.suggestions.find((x) => x.id === suggestion.id).status, 'accepted')
  assert.deepEqual(view.automation.strategy_ids, [seed.strategy.id])
  check('explicit-acceptance', '单独确认后才保存候选，未扩大既有后台计划证券范围')
  report.status = 'passed'
} catch (error) {
  report.status = 'failed'; report.error = error instanceof Error ? error.message : String(error)
  process.exitCode = 1
} finally {
  controller.abort(); await stop()
  report.stopped_at = new Date().toISOString()
  report.runtime_sha256 = createHash('sha256').update(await readFile(runtimeFile)).digest('hex')
  await writeFile(join(instance, 'sidecar.log'), apiLog, { mode: 0o600 })
  await writeFile(join(instance, 'report.json'), JSON.stringify(report, null, 2), { mode: 0o600 })
  await writeFile(join(output, 'latest.json'), JSON.stringify({ instance, report: join(instance, 'report.json'), status: report.status }), { mode: 0o600 })
  process.off('SIGINT', stopSignal); process.off('SIGTERM', stopSignal)
  console.log(`策略 DSH 装配 ${report.status}；合成模型/事件；报告：${join(instance, 'report.json')}`)
  if (report.error) console.error(report.error)
}
