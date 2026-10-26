import assert from 'node:assert/strict'
import { spawn, type ChildProcess } from 'node:child_process'
import { once } from 'node:events'
import { join, resolve } from 'node:path'
import { readFile, writeFile, readdir } from 'node:fs/promises'
import { setTimeout as delay } from 'node:timers/promises'
import { readInstance, request, packageRoot, profileName, runProcess } from '../distribution/instance.js'
import { workerLoop } from '../distribution/worker.js'
import { fileURLToPath } from 'node:url'

const self = fileURLToPath(import.meta.url)
const directory = resolve(process.argv[3] ?? process.argv[2] ?? '')
const config = await readInstance(directory)
if (process.argv[2] === '--worker') {
  const controller = new AbortController()
  process.on('SIGTERM', () => controller.abort())
  process.on('SIGINT', () => controller.abort())
  await workerLoop(config, controller.signal)
} else {
  config.provider = 'huohuo-test'; config.model = 'fixture'
  await writeFile(join(directory, 'instance.json'), JSON.stringify(config), { mode: 0o600 })
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
  const startSidecar = () => spawn(config.python, ['-c', `
import json, sys, time
from huohuo.server import Service
from huohuo.research import snapshot
config=json.load(open(sys.argv[1]))
def fixture(scope):
    time.sleep(2)
    return snapshot(scope, lambda _: ({"data":{"diff":[{"f12":scope["entity_id"].split(":")[-1],"f14":"合成装配样本","f2":12.1,"f18":10,"f124":1792569600}]}}, "https://example.invalid/assembly-fixture"))
Service(config, researcher=fixture).serve_forever()
`, join(directory, 'instance.json')], { env: { ...process.env, PYTHONPATH: join(packageRoot, 'sidecar') }, stdio: 'inherit' })
  async function stop(child: ChildProcess) {
    if (child.exitCode !== null || child.signalCode !== null) return
    const exited = once(child, 'exit')
    child.kill('SIGTERM')
    const timeout = setTimeout(() => child.kill('SIGKILL'), 10_000)
    await exited
    clearTimeout(timeout)
  }
  async function healthy() {
    for (let i = 0; i < 50; i++) { try { await request(config, '/health'); return } catch { await delay(100) } }
    throw new Error('sidecar not ready')
  }
  let sidecar = startSidecar()
  let worker: ChildProcess | undefined
  try {
    await healthy()
    const body = { request_key: 'assembly-one', scope: { entity_id: 'SEC:CN:A:600519', exchange: 'SSE', operation: 'quote_snapshot' }, question: '解释本次快照和数据限制。' }
    const input = join(directory, 'request.json')
    await writeFile(input, JSON.stringify(body))
    worker = spawn(process.execPath, [self, '--worker', directory], { stdio: 'inherit' })
    // 提交客户端是独立进程；退出后后台继续完成。
    await runProcess(process.execPath, [join(packageRoot, 'lib/distribution/cli.js'), 'submit', directory, input], directory)
    let current = await request(config, '/executions', body)
    const id = current.execution_id
    for (let i = 0; i < 180 && ['queued', 'running'].includes(current.status); i++) {
      await delay(500)
      current = await request(config, '/executions/' + id)
    }
    assert.equal(current.status, 'succeeded', JSON.stringify(current))
    const evidence = await request(config, `/executions/${id}/evidence`)
    assert.equal(evidence[0].values.change_percent, '21.0000')
    assert.equal(evidence[0].values.price, '12.1')
    assert.equal(evidence[0].source, 'eastmoney')
    assert.ok(evidence[0].source_url.includes('example.invalid'))
    const proof = JSON.parse(await readFile(join(directory, 'runs', current.current_attempt, 'test-proof.json'), 'utf8'))
    assert.equal(proof.root_guard, true); assert.equal(proof.agent_scope_guard, true); assert.equal(proof.skill_loaded, true)
    assert.deepEqual(proof.tool_names, ['read_security_snapshot'])
    assert.deepEqual(proof.blocked_calls, ['bash', 'write', 'web_fetch', 'subagent', 'run_code'])
    const events = await request(config, `/executions/${id}/events`)
    assert.ok(events.some((event: any) => event.kind === 'runtime.accepted'))
    await stop(worker); worker = undefined
    config.model = 'truncated-fixture'
    await writeFile(join(directory, 'instance.json'), JSON.stringify(config), { mode: 0o600 })
    worker = spawn(process.execPath, [self, '--worker', directory], { stdio: 'inherit' })
    let truncated = await request(config, '/executions', { ...body, request_key: 'assembly-truncated' })
    for (let i = 0; i < 180 && ['queued', 'running'].includes(truncated.status); i++) {
      await delay(500)
      truncated = await request(config, '/executions/' + truncated.execution_id)
    }
    assert.equal(truncated.status, 'failed', JSON.stringify(truncated))
    assert.match(truncated.result.error, /max-tokens/)
    assert.equal((await request(config, `/executions/${truncated.execution_id}/evidence`))[0].status, 'ok')
    await stop(worker); worker = undefined
    await stop(sidecar)
    sidecar = startSidecar()
    await healthy()
    assert.deepEqual(await request(config, '/executions/' + id), current)
    const report = { version: '1.0.0', dsh: '0.2.1-rc.2', status: 'passed', model: 'deterministic fixture', data: 'synthetic fixture',
      real_components: ['npm installation', 'DSH profile/bundle/Skill', 'SDK subprocess', 'tool registry', 'Python API', 'Decimal calculation', 'SQLite'],
      client_exit_did_not_stop_worker: true, sidecar_restart_preserved_result: true,
      valid_json_after_max_tokens_rejected: true, proof, execution_id: id }
    await writeFile(join(directory, 'assembly-report.json'), JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report, null, 2))
  } finally { if (worker) await stop(worker); await stop(sidecar) }
}
