import { request, type Instance } from './instance.js'

type Attempt = { execution_id: string; attempt_id: string; lease_token: string }
type Phase = 'prepare' | 'submit'
export const admissionPolicy = 'hook-model-gate-v1'
export interface Admission {
  mode: 'model' | 'program' | 'blocked'
  reason: string
  detail?: string
  policy: 'hook-model-gate-v1'
  execution_id: string
  attempt_id: string
  phase: Phase
}

/** 不相信领取载荷中的布尔标记；每次由侧车重验正式事件与当前能力。 */
export async function modelAdmission(config: Instance, job: Attempt, phase: Phase): Promise<Admission> {
  const result = await request(config, `/worker/attempts/${encodeURIComponent(job.attempt_id)}/model-admission`, { phase }, 'worker', job.lease_token)
  if (!result || result.policy !== admissionPolicy || result.execution_id !== job.execution_id
      || result.attempt_id !== job.attempt_id || result.phase !== phase
      || !['model', 'program', 'blocked'].includes(result.mode) || typeof result.reason !== 'string') {
    throw Error('模型准入回执缺失或绑定不一致；不启动模型')
  }
  return result
}

export async function rejectModel(config: Instance, job: Attempt, decision: Admission, strategy = false): Promise<void> {
  const path = `/worker/attempts/${encodeURIComponent(job.attempt_id)}`
  const error = `后台模型未获准入：${decision.detail || decision.reason}。未调用模型；请核对委托触发约定或资料状态。`
  await request(config, path + (strategy ? '/strategy-result' : '/finish'), { status: 'failed', error }, 'worker', job.lease_token)
}
