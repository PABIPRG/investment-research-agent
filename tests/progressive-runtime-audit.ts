import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import type { Context } from '@deepseek-ai/cordis'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import { scenarios } from './progressive-model.js'
import { chatSkillNames } from '../product/chat/policy.js'
export const inject = ['agents', 'agentPresets', 'skills', 'systemPrompt']
export function apply(ctx: Context) {
  const host = ctx as any
  setTimeout(() => { void run().catch(e=>writeFile(process.env.HUOHUO_SKILLS_REPORT!,JSON.stringify({status:'failed',error:String(e)}))) }, 0)
  async function run() {
    const results = []
    const api = async (path: string) => { const r = await fetch(process.env.HUOHUO_CHAT_API+path,{headers:{Authorization:`Bearer ${process.env.HUOHUO_USER_TOKEN}`}}); assert.equal(r.status,200); return r.json() as any }
    const before = { mandates: await api('/mandates'), investment: await api('/investment') }
    for (const [id, input] of scenarios) {
      const handle = await ctx.agents.create({ sessionId: randomUUID() as any, meta:{cwd:process.cwd(),agentPreset:'huohuo'},agentOptions:{provider:'huohuo-skills-fixture',model:'controlled'},setup: async c=>{await host.agentPresets.mount(c,'huohuo')} })
      try {
        const a = handle.agent
        const catalog = await ctx.skills.list({scope:a,cwd:process.cwd()})
        assert.deepEqual(catalog.map(s=>s.name).sort(), [...chatSkillNames].sort(), '只能发现产品自带 Skill')
        const prompt = await ctx.systemPrompt.assemble({agent:a,scope:a})
        assert.ok(prompt.sections.some(s=>s.name==='huohuo:invariants'))
        assert.ok(!prompt.sections.some(s=>s.name==='huohuo:research-chat'))
        a.followup(createUserMessage({content:[{type:'text',text:`回放 ${id}：${input}`}],source:{kind:'user'}}))
        await a.whenIdle()
        const proof=(await readFile(process.env.HUOHUO_SKILLS_PROOF!,'utf8')).trim().split('\n').map(x=>JSON.parse(x)).filter(x=>x.session===a.id)
        assert.equal(proof.at(-1)?.status,'completed', `${id} 未完成：${JSON.stringify(a.session.snapshotEvents().slice(-3))}`)
        results.push({id,input,status:'passed',calls:proof.filter(p=>p.call).map(p=>p.call),system_bytes:proof[0].system_bytes,schema_bytes:proof[0].schema_bytes})
      } finally { await handle.dispose() }
    }
    const executions=await api('/executions')
    assert.equal(executions.executions.length,1);assert.equal(executions.executions[0].status,'cancelled')
    assert.deepEqual(await api('/mandates'),before.mandates);assert.deepEqual(await api('/investment'),before.investment)
    const denied=await fetch(process.env.HUOHUO_CHAT_API+'/investment');assert.equal(denied.status,403)
    await writeFile(process.env.HUOHUO_SKILLS_REPORT!,JSON.stringify({status:'passed',model:'controlled fixture',provider:'synthetic directory, no remote calls',cases:results,side_effects:{executions:1,status:'cancelled',mandates_unchanged:true,investment_unchanged:true},unauthorized_http:403,real_model:'not-tested',cost:'not-tested'},null,2))
  }
}
