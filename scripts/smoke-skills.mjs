// 可重复源码装配验收；受控模型，独立数据，不启动旧实例。
import assert from 'node:assert/strict'
import {mkdir,readFile,writeFile,symlink,mkdtemp,copyFile,realpath} from 'node:fs/promises'
import {spawn} from 'node:child_process'
import {join,resolve} from 'node:path'
import {fileURLToPath} from 'node:url'
import {randomBytes,randomUUID} from 'node:crypto'
import {setTimeout as delay} from 'node:timers/promises'
import {checkChatPort} from '../lib/distribution/chat.js'
import {workerLoop} from '../lib/distribution/worker.js'
import {resolvePython} from '../runtime/python.mjs'
const root=fileURLToPath(new URL('../',import.meta.url)),out=join(root,'artifacts/skills-smoke')
const business=process.argv.includes('--business')
if(business&&!process.argv.includes('--serve'))throw Error('业务交互回放必须 --serve，由真实用户交互确认')
const keep=process.argv.includes('--serve'),port=Number(process.env.HUOHUO_SMOKE_PORT??18810),webPort=Number(process.env.HUOHUO_SMOKE_WEB_PORT??18811)
assert.notEqual(port,webPort)
await mkdir(out,{recursive:true});await checkChatPort(port);await checkChatPort(webPort)
const base=resolve(process.env.HUOHUO_SMOKE_TMP??join(out,'instances'));await mkdir(base,{recursive:true})
const instance=await mkdtemp(join(base,'skills-'))
const python=await resolvePython()
const config={version:1,host:'127.0.0.1',port,principal:randomUUID(),user_token:randomBytes(32).toString('base64url'),worker_token:randomBytes(32).toString('base64url'),database:join(instance,'business.sqlite'),dsh_home:join(instance,'dsh'),workspace:join(instance,'workspace'),provider:'huohuo-test',model:'demo-fixture',python:python.executable}
await mkdir(config.workspace,{recursive:true});await writeFile(join(instance,'instance.json'),JSON.stringify(config),{mode:0o600})
// 故意放外部 Skill：必须既不出现在目录，也不能加载。
const rogue=join(config.workspace,'.agents/skills/external-skill');await mkdir(rogue,{recursive:true});await writeFile(join(rogue,'SKILL.md'),'---\nname: external-skill\ndescription: forbidden fixture\n---\nMUST NOT LOAD\n')
const modules=join(root,'node_modules');await mkdir(join(modules,'@huohuo'),{recursive:true})
async function link(target,path){try{await symlink(target,path,'dir')}catch(e){if(e.code!=='EEXIST'||await realpath(path)!==await realpath(target))throw e}}
await link(root,join(modules,'@huohuo/research-agent'));await link(join(root,'ui'),join(modules,'@huohuo/chat-ui'))
const workerProfile=join(config.dsh_home,'profiles/huohuo-worker'),chatProfile=join(config.dsh_home,'profiles/huohuo-chat')
for(const [dir,bundles] of [[workerProfile,['@deepseek-ai/dsh-base','@deepseek-ai/dsh-sdk-app','@huohuo/research-agent']],[chatProfile,['@deepseek-ai/dsh-base','@deepseek-ai/dsh-web-app','@huohuo/chat-bundle']]]){
 await mkdir(dir,{recursive:true});await link(modules,join(dir,'node_modules'))
 await writeFile(join(dir,'package.json'),JSON.stringify({name:'huohuo-smoke-profile',private:true,dsh:{profile:{bundles}}}))
}
// Stable source-local bundle link; its content is the current product patch.
const bundle=join(out,'chat-bundle');await mkdir(bundle,{recursive:true})
await writeFile(join(bundle,'package.json'),JSON.stringify({name:'@huohuo/chat-bundle',version:'1.0.0',private:true,dsh:{bundle:{patch:'./cordis.patch.yml'}},engines:{dsh:'0.2.1-rc.2'}}))
await copyFile(join(root,'product/bundle/chat.patch.yml'),join(bundle,'cordis.patch.yml'));await link(bundle,join(modules,'@huohuo/chat-bundle'))
const disabled='- id: ui-settings-models\n  config:\n    credentialOnboarding: false\n- id: llm-deepseek\n  disabled: true\n- id: llm-deepseek-account\n  disabled: true\n- id: llm-pi-ai\n  disabled: true\n'
await writeFile(join(workerProfile,'cordis.patch.yml'),disabled+`- insert:\n    - id: controlled-worker-model\n      name: '${join(root,'lib/tests/followup-model.js')}'\n`)
await writeFile(join(chatProfile,'cordis.patch.yml'),disabled+`- id: agent-default-model\n  config:\n    provider: huohuo-skills-fixture\n    model: controlled\n- insert:\n    - id: controlled-chat-model\n      name: '${join(root,business?'lib/tests/business-model.js':'lib/tests/progressive-model.js')}'\n${keep?'':`    - id: controlled-audit\n      name: '${join(root,'lib/tests/progressive-runtime-audit.js')}'\n`}`)
const proof=join(instance,'proof.jsonl'),report=join(instance,'report.json')
const env={PATH:process.env.PATH,HOME:join(instance,'home'),TMPDIR:join(instance,'tmp'),LANG:'en_US.UTF-8',DSH_TELEMETRY_DISABLED:'1',DSH_HOME:config.dsh_home,HUOHUO_SKILLS_PROOF:proof,HUOHUO_SKILLS_REPORT:report}
await mkdir(env.TMPDIR,{recursive:true});await mkdir(env.HOME,{recursive:true})
const controller=new AbortController();let api,web,worker;let closing=false;let webLog=''
async function stop(p){if(!p||p.exitCode!==null||p.signalCode!==null)return;const done=new Promise(r=>p.once('exit',r));p.kill('SIGTERM');const timer=setTimeout(()=>p.kill('SIGKILL'),5000);await done;clearTimeout(timer)}
async function cleanup(){if(closing)return;closing=true;controller.abort();await worker?.catch(()=>{});await stop(web);await stop(api);await writeFile(join(out,'runtime-stopped.json'),JSON.stringify({stopped_at:new Date().toISOString(),ports:[port,webPort]}));await writeFile(join(out,'runtime.log'),webLog)}
const interrupted=()=>{void cleanup().then(()=>process.exit(130))};process.on('SIGTERM',interrupted);process.on('SIGINT',interrupted)
try{
 api=spawn(config.python,[join(root,'tests/night_research_server.py'),join(instance,'instance.json')],{cwd:root,env:{...env,PYTHONPATH:join(root,'sidecar'),PYTHONDONTWRITEBYTECODE:'1'},stdio:['pipe','pipe','pipe']})
 let apiLog='';api.stderr.on('data',d=>apiLog+=d)
 await new Promise((res,rej)=>{const t=setTimeout(()=>rej(Error('API startup timed out')),15000);api.stdout.once('data',()=>{clearTimeout(t);res()});api.once('exit',()=>{clearTimeout(t);rej(Error(apiLog))});api.once('error',rej)})
 if(keep)worker=workerLoop(config,controller.signal).catch(e=>{if(!controller.signal.aborted)throw e})
 let launchUrl
 web=spawn(process.execPath,[join(modules,'@deepseek-ai/dsh/lib/bin.js'),'--profile','huohuo-chat','--host','127.0.0.1','--port',String(webPort),'--no-open'],{cwd:config.workspace,env:{...env,HUOHUO_CHAT_API:`http://127.0.0.1:${port}`,HUOHUO_USER_TOKEN:config.user_token,HUOHUO_CHAT_WEB_ORIGIN:`http://127.0.0.1:${webPort}`},stdio:['ignore','pipe','pipe']})
 for(const stream of [web.stdout,web.stderr])stream.on('data',d=>{const raw=String(d);launchUrl??=raw.match(/http:\/\/127\.0\.0\.1:\d+\/\?token=[^\s\u001b]+/)?.[0];webLog+=raw.replace(/\?token=[^\s\u001b]+/g,'?token=[redacted]')})
 for(let i=0;i<300&&!launchUrl;i++){if(web.exitCode!==null)throw Error('Web exited: '+webLog.slice(-4000));await delay(100)}
 assert.ok(launchUrl,'Web startup timed out: '+webLog.slice(-4000))
 await writeFile(join(out,'runtime.json'),JSON.stringify({instance,launchUrl,api:port,web:webPort,model:'controlled',provider:'synthetic',source_linked:true}),{mode:0o600})
 if(keep){console.log('内部回放环境已就绪：仅接受回放编号，不支持自然语言或填写真实 API Key。用户冒烟请使用 docs/启动指引.md 的持久实例入口。回放入口存于 artifacts/skills-smoke/runtime.json；Ctrl+C 只停止本次服务。');await new Promise(r=>controller.signal.addEventListener('abort',r,{once:true}))}
 else{
  let result
  for(let i=0;i<1200;i++){try{result=JSON.parse(await readFile(report,'utf8'));break}catch{}await delay(100)}
  assert.ok(result,'回放超时：'+webLog.slice(-3000));await copyFile(report,join(out,'report.json'));await copyFile(proof,join(out,'proof.jsonl')).catch(e=>{if(e.code!=='ENOENT')throw e})
  assert.equal(result.status,'passed',JSON.stringify(result));console.log(`Skill 原生装配：${result.cases.length} 项回放 passed，业务副作用已核对。`)
 }
}catch(e){console.error(e);process.exitCode=1}finally{await cleanup()}
