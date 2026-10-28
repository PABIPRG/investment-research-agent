import { HarnessClient, type HarnessNotification } from '@deepseek-ai/dsh-sdk-client'
import { mkdir, readFile } from 'node:fs/promises'
import { join, dirname } from 'node:path'
import { randomUUID } from 'node:crypto'
import { setTimeout as delay } from 'node:timers/promises'
import { type Instance, InstanceApiError, profileName, request } from './instance.js'
import { activityObservation, type RuntimeObserver } from './observation.js'
import { strategyLoop } from './strategy-worker.js'
import { boundedManifest } from '../product/tools/bounded-operations.js'

export function runtimeEnvironment(config: Instance): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {}
  // 不把整个父进程环境（CI、云凭据、user/worker token）交给模型运行时。
  for (const name of ['PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY',
    'https_proxy', 'http_proxy', 'no_proxy', 'DEEPSEEK_API_KEY']) {
    if (process.env[name] !== undefined) env[name] = process.env[name]
  }
  return { ...env, DSH_HOME: config.dsh_home, DSH_TELEMETRY_DISABLED: '1', DSH_PRIMARY_RUNTIME: '', DSH_BUNDLED_OFFICE_CLI: '' }
}

export function resultFromActivity(events: any[]): unknown {
  const end = events.findLast(event => event.type === 'turn/end')
  const assistant = events.findLast(event => event.type === 'assistant/message')
  if (!end || end.data?.reason?.kind !== 'completed' || !assistant || assistant.data?.interrupted === true
      || assistant.data?.turn !== end.data?.turn) {
    return { status: 'failed', error: '研究活动未完整结束：' + (end?.data?.reason?.kind ?? 'missing_terminal_event') }
  }
  const response = assistant.data.message.content.filter((block: any) => block.type === 'text').map((block: any) => block.text).join('')
  try { return JSON.parse(response) } catch { return { status: 'failed', error: '模型输出不符合研究结果 JSON 契约' } }
}

// 仅映射已核对的 finish 事务提交前校验；未知错误不等于结果未提交。
const finishRejections: Record<string, string> = {
  '409:conflict:result binding or evidence missing': '研究结果与本次范围不一致或缺少证据',
  '409:conflict:result references unavailable evidence': '研究结果引用的证据不可用',
  '409:conflict:result binding mismatch': '研究结果与本次执行或范围不一致',
  '409:conflict:judgement references unbound evidence': '条件判断引用了未绑定的证据',
  '409:conflict:definite judgement requires evidence': '确定性条件判断缺少证据',
  '409:conflict:financial source unit and basis are unverified; judgement must be unknown': '财务来源单位与口径未经核验，不能形成确定性判断',
  '400:invalid_request:invalid execution result': '研究结果不符合结果契约',
  '400:invalid_request:result too large': '研究结果超过允许大小',
  '400:invalid_request:invalid summary': '研究摘要缺失或超出允许长度',
  '400:invalid_request:invalid evidence id': '研究证据标识无效',
  '400:invalid_request:invalid error': '研究失败结果缺少有效原因',
  '400:invalid_request:invalid contact suggestion': '联系建议结构无效',
  '400:invalid_request:invalid judgements': '条件判断结构无效',
  '400:invalid_request:invalid research judgement': '条件判断值无效',
  '400:invalid_request:financial evidence scope mismatch': '财务证据与本次研究范围不一致',
  '400:invalid_request:financial evidence subject mismatch': '财务证据的研究主体不一致',
  '400:invalid_request:financial evidence source hash mismatch': '财务证据来源指纹不一致',
  '400:invalid_request:financial evidence semantics mismatch': '财务证据指标或口径不一致',
  '400:invalid_request:financial evidence source mismatch': '财务证据来源不一致',
  '400:invalid_request:financial evidence observation time missing': '财务证据缺少有效采集时间',
  '400:invalid_request:provider_schema_invalid': '财务来源数据结构无效',
  '400:invalid_request:requested_period_or_metric_not_covered': '财务来源不覆盖所需报告期或指标',
  '400:invalid_request:requested_metric_ambiguous': '财务来源中的指标有歧义',
  '400:invalid_request:requested_value_unavailable': '财务来源中的所需数值不可用',
}

export async function finishAttempt(config: Instance, job: any, result: unknown, canCommit: () => boolean = () => true): Promise<any> {
  const path = `/worker/attempts/${job.attempt_id}`
  if (!canCommit()) throw new Error('研究执行已停止；不提交结果')
  try { return await request(config, path + '/finish', result, 'worker', job.lease_token) }
  catch (error) {
    const reason = error instanceof InstanceApiError ? finishRejections[`${error.status}:${error.apiCode}:${error.detail}`] : undefined
    if (!reason || !canCommit()) throw error
    // 同一能力确认仍有效；暂停/过期与写入之间的竞态仍由 finish 事务内校验阻断。
    const lease = await request(config, path + '/heartbeat', {}, 'worker', job.lease_token)
    if (!canCommit() || typeof lease?.lease_until !== 'number' || !Number.isFinite(lease.lease_until) || lease.lease_until <= Date.now() / 1000) throw error
    // 只提交失败回执一次。此请求丢失回执时仍交原 uncertain 路径，不重跑或自动重报。
    return request(config, path + '/finish', { status: 'failed', error: `研究结果未通过业务校验：${reason}。` }, 'worker', job.lease_token)
  }
}

export async function runAttempt(config: Instance, job: any, signal: AbortSignal, observer?: RuntimeObserver): Promise<'completed' | 'uncertain'> {
  const emit = (kind: string, data: Record<string, unknown> = {}) => {
    // 观察消费者故障不能改变任务执行或结果提交。
    try { observer?.({ ...data, kind, observed_at: new Date().toISOString(), execution_id: job.execution_id, attempt_id: job.attempt_id }) } catch { /* 观察为可选。 */ }
  }
  const sessionId = randomUUID()
  const runDir = join(dirname(config.database), 'runs', job.attempt_id)
  await mkdir(runDir, { recursive: true, mode: 0o700 })
  const ackPath = join(runDir, 'assembly.json')
  const client = new HarnessClient({ profile: profileName, dshHome: config.dsh_home, processCwd: config.workspace,
    initializeTimeoutMs: 30_000, requestTimeoutMs: 30_000,
    env: { ...runtimeEnvironment(config), HUOHUO_TOOL_API: `http://127.0.0.1:${config.port}`,
      HUOHUO_ATTEMPT_ID: job.attempt_id, HUOHUO_ATTEMPT_TOKEN: job.lease_token,
      HUOHUO_RUNTIME_ACK_PATH: ackPath,
      HUOHUO_EXECUTION_BINDING: JSON.stringify({ execution_id: job.execution_id, scope: job.scope }) } })
  const subscription = client.subscribeSessionTree(sessionId)
  const path = `/worker/attempts/${job.attempt_id}`
  const stopped = new AbortController()
  let enqueued = false
  let submitting = false
  const close = () => { stopped.abort(); void client.close().catch(() => {}) }
  signal.addEventListener('abort', close, { once: true })
  const deadline = setTimeout(close, 120_000)
  const heartbeat = (async () => {
    while (!stopped.signal.aborted) {
      try {
        await delay(5_000, undefined, { signal: stopped.signal })
        await request(config, path + '/heartbeat', {}, 'worker', job.lease_token)
      } catch { if (!stopped.signal.aborted) close(); return }
    }
  })()
  try {
    if (signal.aborted) throw new Error('worker stopping')
    emit('runtime.starting', { profile: profileName })
    client.start()
    const initialized = await client.initialize({ cwd: config.workspace, provider: config.provider, model: config.model })
    const ack = JSON.parse(await readFile(ackPath, 'utf8'))
    if (ack.execution_id !== job.execution_id || ack.version !== '1.0.0' || ack.policy !== 'bounded-research-v1'
        || JSON.stringify(ack.capability_manifest) !== JSON.stringify(boundedManifest)
        || JSON.stringify(ack.tools) !== '["read_security_snapshot"]' || !ack.skill_sha256
        || ack.runtime?.profile?.name !== profileName) throw new Error('required bundle not loaded')
    emit('runtime.initialized', { runtime: ack.runtime, server: initialized.serverInfo, tools: ack.tools, skill_sha256: ack.skill_sha256 })
    submitting = true
    const messageId = await client.prompt(sessionId, [{ type: 'text', text: job.question + (job.investment_facts ? '\n本次只读投资事实快照（不扩大已确认研究证券范围）：' + JSON.stringify(job.investment_facts) : '') }])
    enqueued = true
    emit('prompt.accepted', { session_id: sessionId, message_id: messageId })
    await request(config, path + '/runtime', { session_id: sessionId, message_id: messageId }, 'worker', job.lease_token)
    let received = false
    const events: any[] = []
    while (true) {
      const event: HarnessNotification = await subscription.next()
      if (event.params.sessionId !== sessionId) continue
      const payload = event.params.event as any
      if (!received) {
        if (event.method !== 'session.event' || payload?.type !== 'agent/inbox/spliced'
            || !payload.data?.inserted?.some((message: any) => message.id === messageId)) continue
        received = true
      }
      if (event.method === 'session.event') {
        events.push(payload)
        if (observer) {
          try {
            const observation = activityObservation(payload)
            if (observation) emit(String(observation.kind), observation)
          } catch { /* 异常观察事件不改变实际研究的结果判断。 */ }
        }
      }
      if (event.method === 'session.status' && event.params.status === 'idle') break
    }
    const result = resultFromActivity(events)
    // 业务端再次验证 execution、Scope、证据及 attempt；模型没有直接写库权限。
    const committed = await finishAttempt(config, job, result, () => !signal.aborted && !stopped.signal.aborted)
    emit('execution.committed', { status: committed.status })
    return 'completed'
  } catch {
    emit('runtime.unsettled', { enqueued, submitting })
    if (!enqueued && !submitting && !signal.aborted && !stopped.signal.aborted) {
      await request(config, path + '/finish', { status: 'failed', error: '研究运行时初始化或必要装配检查失败' }, 'worker', job.lease_token).catch(() => {})
    }
    // 发送后的异常可能已经执行，留待租约过期标记 interrupted；绝不静默重放。
    return 'uncertain'
  } finally {
    clearTimeout(deadline)
    signal.removeEventListener('abort', close)
    stopped.abort()
    subscription.close()
    await heartbeat
    await client.close()
    emit('runtime.closed')
  }
}

export async function workerLoop(config: Instance, signal: AbortSignal, observer?: RuntimeObserver): Promise<void> {
  const workerId = randomUUID(), stop = new AbortController()
  const stopping = () => stop.abort()
  signal.addEventListener('abort', stopping, { once: true })
  if (signal.aborted) stop.abort()
  const strategies = strategyLoop(config, workerId + ':strategies', stop.signal)
  try {
    while (!stop.signal.aborted) {
      await request(config, '/worker/recover', {}, 'worker', undefined, stop.signal)
      try { await request(config, '/worker/discover', {}, 'worker', undefined, stop.signal) }
      catch { if (stop.signal.aborted) break /* 来源失败不会阻塞已有研究领取。 */ }
      const job = await request(config, '/worker/claim', { worker_id: workerId }, 'worker', undefined, stop.signal)
      if (job) await runAttempt(config, job, stop.signal, observer)
      else await delay(500, undefined, { signal: stop.signal }).catch(() => {})
    }
  } finally {
    stop.abort(); signal.removeEventListener('abort', stopping); await strategies
  }
}
