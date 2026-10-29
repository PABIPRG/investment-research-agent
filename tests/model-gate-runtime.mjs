// 实际 worker → 实际侧车 HTTP；仅模型 SDK 使用计数夹具，绝不请求 provider。
import { readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
const [library, configPath] = process.argv.slice(2)
const config = JSON.parse(await readFile(configPath, 'utf8'))
const { runAttempt } = await import(pathToFileURL(join(library, 'distribution/worker.js')))
const { boundedManifest } = await import(pathToFileURL(join(library, 'product/tools/bounded-operations.js')))
const base = `http://127.0.0.1:${config.port}`
async function post(path, body, token) {
  const response = await fetch(base + path, { method: 'POST', headers: {
    Authorization: `Bearer ${token}`, 'Content-Type': 'application/json',
  }, body: JSON.stringify(body) })
  if (!response.ok) throw Error(`本地夹具接口失败 ${path}: ${response.status}`)
  return response.json()
}
const job = await post('/worker/claim', { worker_id: 'runtime-gate-fixture', admission_policy: 'hook-model-gate-v1' }, config.worker_token)
if (!job) {
  console.log(JSON.stringify({ no_job: true, constructed: 0, started: 0, prompted: 0 }))
} else {
  let constructed = 0, started = 0, prompted = 0, eventIndex = 0, result
  const factory = options => {
    constructed++
    return {
      start() { started++ }, close: async () => {},
      initialize: async () => {
        await writeFile(options.env.HUOHUO_RUNTIME_ACK_PATH, JSON.stringify({ execution_id: job.execution_id,
          version: '1.0.0', policy: 'bounded-research-v1', capability_manifest: boundedManifest,
          tools: ['read_security_snapshot'], skill_sha256: 'synthetic', runtime: { profile: { name: 'huohuo-worker' } } }))
        if (config.pause) await post(`/mandates/${config.pause.mandate_id}/pause`, config.pause.body, config.user_token)
        return { serverInfo: { fixture: true } }
      },
      prompt: async () => {
        prompted++
        const evidence = await post(`/attempts/${job.attempt_id}/research`, {}, job.lease_token)
        result = { status: 'succeeded', execution_id: job.execution_id, scope: job.scope,
          evidence_ids: [evidence.evidence_id], summary: '受控模型：有效 Hook 后的一次研究' }
        return 'synthetic-message'
      },
      subscribeSessionTree: sessionId => ({ close() {}, next: async () => {
        const events = [
          { method: 'session.event', event: { type: 'agent/inbox/spliced', data: { inserted: [{ id: 'synthetic-message' }] } } },
          { method: 'session.event', event: { type: 'assistant/message', data: { turn: 1, message: { content: [{ type: 'text', text: JSON.stringify(result) }] } } } },
          { method: 'session.event', event: { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } } },
          { method: 'session.status', status: 'idle' },
        ]
        const event = events[eventIndex++]
        if (!event) throw Error('合成事件耗尽')
        return { method: event.method, params: { sessionId, event: event.event, status: event.status } }
      } }),
    }
  }
  const outcome = await runAttempt(config, { ...job, allow_model: true, position_rule: true }, new AbortController().signal, undefined, factory)
  console.log(JSON.stringify({ outcome, constructed, started, prompted, execution_id: job.execution_id }))
}
