import assert from 'node:assert/strict'
import { spawn, type ChildProcess } from 'node:child_process'
import { join, resolve } from 'node:path'
import { once } from 'node:events'
import { readFile, writeFile } from 'node:fs/promises'
import { setTimeout as delay } from 'node:timers/promises'
import { randomUUID } from 'node:crypto'
import { readInstance, request } from '../distribution/instance.js'

const directory = resolve(process.argv[2])
const config = await readInstance(directory)
config.provider = 'huohuo-test'; config.model = 'fixture'
await writeFile(join(directory, 'instance.json'), JSON.stringify(config), { mode: 0o600 })
const cli = join(directory, 'dsh/profiles/huohuo-worker/node_modules/@huohuo/research-agent/lib/distribution/cli.js')
const start = () => spawn(process.execPath, [cli, 'serve', directory], { cwd: directory, stdio: ['ignore', 'pipe', 'inherit'] })
async function ready(child: ChildProcess) {
  for (let i = 0; i < 80; i++) {
    if (child.exitCode !== null) throw new Error('service exited')
    try { await request(config, '/health'); return } catch { await delay(100) }
  }
  throw new Error('service not ready')
}
async function gone() {
  for (let i = 0; i < 80; i++) { try { await request(config, '/health'); await delay(100) } catch { return } }
  throw new Error('API still responds after supervisor exit')
}
async function stop(child: ChildProcess, signal: NodeJS.Signals) {
  if (child.exitCode !== null || child.signalCode !== null) return
  const exited = once(child, 'exit')
  child.kill(signal)
  await exited
}
let service = start()
try {
  await ready(service)
  const body = { request_key: 'live-lifecycle-' + randomUUID(), scope: { entity_id: 'SEC:CN:A:600519', exchange: 'SSE', operation: 'quote_snapshot' }, question: '解释报价与数据限制。' }
  let job = await request(config, '/executions', body)
  for (let i = 0; i < 180 && ['queued', 'running'].includes(job.status); i++) { await delay(500); job = await request(config, '/executions/' + job.execution_id) }
  assert.ok(['succeeded', 'failed'].includes(job.status), JSON.stringify(job))
  const evidence = await request(config, `/executions/${job.execution_id}/evidence`)
  assert.equal(evidence[0].source, 'eastmoney')
  if (job.status === 'succeeded') {
    assert.equal(evidence[0].status, 'ok')
    assert.match(evidence[0].source_url, /^https:\/\/push2\.eastmoney\.com\//)
  } else {
    assert.notEqual(evidence[0].status, 'ok')
    assert.match(job.result.error, /真实工具没有取得可用证据/)
  }
  await stop(service, 'SIGKILL')
  await gone()
  service = start()
  await ready(service)
  assert.deepEqual(await request(config, '/executions/' + job.execution_id), job)
  // 新提交先取消排队或刚领取的执行，保证用户版本冲突会显式返回而非静默覆盖。
  const cancelled = await request(config, '/executions', { ...body, request_key: 'lifecycle-cancel-' + randomUUID() })
  let latest = await request(config, '/executions/' + cancelled.execution_id)
  let receipt: any
  for (let i = 0; i < 5; i++) {
    try { receipt = await request(config, `/executions/${latest.execution_id}/cancel`, { expected_revision: latest.revision, request_key: 'cancel-' + i }); break }
    catch { latest = await request(config, '/executions/' + latest.execution_id) }
  }
  assert.equal(receipt?.status, 'cancelled')
  await delay(6_000)
  assert.equal((await request(config, '/executions/' + cancelled.execution_id)).status, 'cancelled')
  await stop(service, 'SIGTERM')
  await gone()
  const report = { status: 'passed', model: 'deterministic fixture', data: 'live Eastmoney', execution_id: job.execution_id,
    actual_cli_serve: true, api_stopped_after_idle_supervisor_sigkill: true, restart_preserved_result: true, cancel_persisted: true,
    live_source_status: evidence[0].status, live_source_error: evidence[0].error_type ?? null,
    source_hash: evidence[0].source_hash, data_as_of: evidence[0].data_as_of, observed_at: evidence[0].observed_at }
  await writeFile(join(directory, 'lifecycle-report.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} finally { await stop(service, 'SIGTERM') }
