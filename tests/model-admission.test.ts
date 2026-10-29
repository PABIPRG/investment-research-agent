import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, writeFile, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { runAttempt, type RuntimeFactory } from '../distribution/worker.js'
import { runStrategyPlanner, type StrategyPlannerJob } from '../distribution/strategy-worker.js'
import { profileName, type Instance } from '../distribution/instance.js'
import { boundedManifest } from '../product/tools/bounded-operations.js'

const job = { execution_id: 'execution', attempt_id: 'attempt', lease_token: 'synthetic-only' }
const config = { host: '127.0.0.1', port: 1, worker_token: 'synthetic-only' } as Instance

for (const strategy of [false, true]) {
  for (const mode of ['blocked', 'program', 'missing', 'wrong-binding', 'old-server'] as const) {
    test(`${strategy ? '策略' : '普通'} worker ${mode} 时模型构造/启动/请求均为零`, async () => {
      const previous = globalThis.fetch
      const calls: string[] = []
      let constructed = 0
      const factory: RuntimeFactory = () => { constructed++; throw Error('不应构造模型运行时') }
      globalThis.fetch = async (input, options) => {
        const path = new URL(String(input)).pathname; calls.push(path)
        if (path.endsWith('/model-admission')) {
          if (mode === 'old-server') return Response.json({ error: 'not_found' }, { status: 404 })
          if (mode === 'missing') return Response.json({})
          const phase = JSON.parse(options?.body as string).phase
          return Response.json({ ...job, policy: 'hook-model-gate-v1', mode: mode === 'wrong-binding' ? 'model' : mode,
            reason: 'test', phase, execution_id: mode === 'wrong-binding' ? 'other' : job.execution_id })
        }
        return Response.json({ status: 'failed' })
      }
      try {
        // 领取载荷伪造为已允许或持仓任务，也不能跳过正式门禁。
        const run = () => strategy
          ? runStrategyPlanner(config, { ...job, action: 'candidate', allow_model: true } as unknown as StrategyPlannerJob, new AbortController().signal, factory)
          : runAttempt(config, { ...job, position_rule: true, allow_model: true }, new AbortController().signal, undefined, factory)
        if (['missing', 'wrong-binding', 'old-server'].includes(mode)) await assert.rejects(run)
        else await run()
        assert.equal(constructed, 0)
        assert.equal(calls[0], '/worker/attempts/attempt/model-admission')
        assert.equal(calls.some(path => path.endsWith('/runtime')), false)
        if (mode === 'program' && !strategy) assert.ok(calls.includes('/worker/attempts/attempt/program-run'))
      } finally { globalThis.fetch = previous }
    })
  }
}

for (const strategy of [false, true]) {
  for (const submitAllowed of [true, false]) {
    test(`${strategy ? '策略' : '普通'} worker 准备获准后提交${submitAllowed ? '获准只请求一次' : '失效不发送请求'}`, async () => {
      const previous = globalThis.fetch
      const root = await mkdtemp(join(tmpdir(), 'huohuo-model-gate-'))
      let constructed = 0, started = 0, prompted = 0, next = 0
      const phases: string[] = []
      const cfg = { ...config, database: join(root, 'business.db'), dsh_home: root, workspace: root } as Instance
      const result = strategy ? { status: 'completed', candidates: [] } : { status: 'failed', error: '合成结果' }
      const runtimeFactory: RuntimeFactory = options => {
        constructed++
        return {
          start() { started++ }, close: async () => {},
          initialize: async () => {
            const ack = strategy
              ? { policy: 'strategy-candidate-v1', job_id: 'job', tools: [], runtime: { profile: { name: 'huohuo-strategy-worker' } } }
              : { policy: 'bounded-research-v1', execution_id: job.execution_id, tools: ['read_security_snapshot'], capability_manifest: boundedManifest,
                skill_sha256: 'synthetic', runtime: { profile: { name: profileName } } }
            await writeFile(options!.env!.HUOHUO_RUNTIME_ACK_PATH!, JSON.stringify({ ...ack, version: '1.0.0' }))
            return { serverInfo: {} }
          },
          prompt: async () => { prompted++; return 'message' },
          subscribeSessionTree: (sessionId: string) => ({ close() {}, next: async () => {
            const events = [
              { method: 'session.event', event: { type: 'agent/inbox/spliced', data: { inserted: [{ id: 'message' }] } } },
              { method: 'session.event', event: { type: 'assistant/message', data: { turn: 1, message: { content: [{ type: 'text', text: JSON.stringify(result) }] } } } },
              { method: 'session.event', event: { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } } },
              { method: 'session.status', status: 'idle' },
            ]
            const e = events[next++]
            assert.ok(e, '运行不能无界等待合成结果')
            return { method: e.method, params: { sessionId, event: e.event, status: e.status } }
          } }),
        } as unknown as ReturnType<RuntimeFactory>
      }
      globalThis.fetch = async (input, options) => {
        if (String(input).endsWith('/model-admission')) {
          const phase = JSON.parse(options?.body as string).phase; phases.push(phase)
          return Response.json({ ...job, phase, policy: 'hook-model-gate-v1',
            mode: phase === 'prepare' || submitAllowed ? 'model' : 'blocked', reason: 'synthetic' })
        }
        return Response.json({ status: 'failed' })
      }
      try {
        const value = strategy
          ? await runStrategyPlanner(cfg, { ...job, job_id: 'job', action: 'candidate', deadline: Date.now() / 1000 + 30, policy: 'strategy-candidate-v1' } as StrategyPlannerJob, new AbortController().signal, runtimeFactory)
          : await runAttempt(cfg, job, new AbortController().signal, undefined, runtimeFactory)
        assert.equal(value, 'completed')
        assert.deepEqual(phases, ['prepare', 'submit'])
        assert.equal(constructed, 1); assert.equal(started, 1)
        assert.equal(prompted, submitAllowed ? 1 : 0)
      } finally { globalThis.fetch = previous; await rm(root, { recursive: true, force: true }) }
    })
  }
}
