// 从最终 tgz 建立仓外 consumer 与两个生产 Profile，复用显式指定的本轮 Python 环境。
import assert from 'node:assert/strict'
import {mkdir,mkdtemp,readFile,writeFile,copyFile,symlink,access} from 'node:fs/promises'
import {join,resolve} from 'node:path'
import {pathToFileURL} from 'node:url'
import {execFile,spawn} from 'node:child_process'
import {promisify} from 'node:util'
import {randomUUID,randomBytes,createHash} from 'node:crypto'
import {setTimeout as delay} from 'node:timers/promises'
const run=promisify(execFile),tgz=resolve(process.argv[2]??''),base=resolve(process.argv[3]??'artifacts/release-check')
assert.ok(process.argv[2]&&process.argv[3],'用法：node scripts/verify-release.mjs <tgz> <独立验证根>')
assert.ok(process.env.HUOHUO_PYTHON,'须指定本次独立准备的 Python 环境')
await mkdir(base,{recursive:true});const reuse=process.env.HUOHUO_RELEASE_CHECK_DIR
const dir=reuse?resolve(reuse):await mkdtemp(join(base,'release-')),consumer=join(dir,'consumer');await mkdir(consumer,{recursive:true})
const digest=createHash('sha256').update(await readFile(tgz)).digest('hex')
if(reuse){assert.equal(JSON.parse(await readFile(join(dir,'release-owner.json'),'utf8')).tarball_sha256,digest,'只能复用相同产物的自有验证目录')}else await writeFile(join(dir,'release-owner.json'),JSON.stringify({tarball_sha256:digest}))
const cache=resolve(process.env.npm_config_cache??join(base,'npm-cache'))
if(!reuse)await writeFile(join(consumer,'package.json'),JSON.stringify({private:true}))
if(!reuse)await run('npm',['install',tgz,'--omit=dev','--ignore-scripts','--no-audit','--no-fund','--prefer-offline','--cache',cache],{cwd:consumer,maxBuffer:8e6})
const installed=join(consumer,'node_modules/@huohuo/research-agent')
const {installWorker}=await import(pathToFileURL(join(installed,'lib/distribution/instance.js')))
const {installChat,checkChatPort}=await import(pathToFileURL(join(installed,'lib/distribution/chat.js')))
const port=Number(process.env.HUOHUO_SMOKE_PORT??18814),webPort=Number(process.env.HUOHUO_SMOKE_WEB_PORT??18815)
await checkChatPort(port);await checkChatPort(webPort)
const instance=join(dir,'instance');await mkdir(join(instance,'cache'),{recursive:true});if(!reuse)await symlink(cache,join(instance,'cache/npm'),'dir')
const config=reuse?JSON.parse(await readFile(join(instance,'instance.json'),'utf8')):{version:1,host:'127.0.0.1',port,principal:randomUUID(),user_token:randomBytes(32).toString('hex'),worker_token:randomBytes(32).toString('hex'),database:join(instance,'business.sqlite3'),dsh_home:join(instance,'dsh'),workspace:join(instance,'workspace'),provider:'deepseek-official',model:'deepseek-flash',python:resolve(process.env.HUOHUO_PYTHON)}
await mkdir(config.workspace,{recursive:true});await copyFile(tgz,join(instance,'product.tgz'));await writeFile(join(instance,'instance.json'),JSON.stringify(config),{mode:0o600})
// 验证锁版本及环境完整性；不是声称再次从空机器完整 init。
await run(config.python,['-c','import importlib.metadata,pathlib,sys\nfor line in pathlib.Path(sys.argv[1]).read_text().splitlines():\n name,version=line.split("==");assert importlib.metadata.version(name)==version,name',join(installed,'sidecar/requirements.lock')]);await run(config.python,['-m','pip','check'])
await installWorker(config);await installChat(config)
await assert.rejects(access(join(installed,'lib/tests/smoke.js')))
await mkdir(join(dir,'home'),{recursive:true});await mkdir(join(dir,'tmp'),{recursive:true})
const cli=join(installed,'lib/distribution/cli.js')
const child=spawn(process.execPath,[cli,'start',instance,String(webPort),'--no-open'],{cwd:consumer,env:{PATH:process.env.PATH,HOME:join(dir,'home'),TMPDIR:join(dir,'tmp'),DSH_TELEMETRY_DISABLED:'1'},stdio:['ignore','pipe','pipe']})
let log='',url;for(const stream of [child.stdout,child.stderr])stream.on('data',d=>{const s=String(d);url??=s.match(/http:\/\/127\.0\.0\.1:\d+\/\?token=[^\s\u001b]+/)?.[0];log+=s.replace(/\?token=[^\s\u001b]+/g,'?token=[redacted]')})
const report={status:'not-tested',tarball_sha256:createHash('sha256').update(await readFile(tgz)).digest('hex'),fresh_python_init:false,model_called:false,ports:[port,webPort]}
try{
 for(let i=0;i<600&&!url;i++){if(child.exitCode!==null)throw Error('start exited '+log.slice(-2000));await delay(100)}
 assert.ok(url,'Web startup timeout '+log.slice(-2000))
 assert.equal((await fetch(`http://127.0.0.1:${port}/health`,{headers:{Authorization:`Bearer ${config.user_token}`}})).status,200)
 const {chromium}=await import(process.env.HUOHUO_PLAYWRIGHT??'playwright')
 const browser=await chromium.launch({headless:true,channel:'chrome'})
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}})
  await page.goto(url)
  await page.getByRole('button',{name:'委托查询',exact:true}).waitFor({timeout:30000})
  const continueButton=page.getByRole('button',{name:'继续',exact:true})
  if(await continueButton.isVisible())await continueButton.click()
  await page.getByText('预览版说明',{exact:true}).waitFor({state:'hidden',timeout:30000})
  await page.getByRole('button',{name:'委托查询',exact:true}).click()
  await page.getByText('还没有委托。',{exact:false}).waitFor({timeout:30000})
  await page.getByRole('button',{name:'刷新记录',exact:true}).click()
  await page.getByText('还没有委托。',{exact:false}).waitFor()
  await page.screenshot({path:join(base,'production-startup.png'),fullPage:true})
 }finally{await browser.close()}
 report.status='passed';report.checks=['production consumer and two profiles installed from tgz','locked Python versions and pip check','installed CLI starts API and authenticated browser entry','preview dialog dismissed; mandate navigation and refresh interactive','test model absent'];
}catch(e){report.status='failed';report.error=String(e);throw e}finally{
 if(child.exitCode===null&&child.signalCode===null){const end=new Promise(r=>child.once('exit',r));child.kill('SIGTERM');const timer=setTimeout(()=>child.kill('SIGKILL'),10000);await end;clearTimeout(timer)}
 await checkChatPort(port);await checkChatPort(webPort);report.ports_released=true
 await writeFile(join(base,'report.json'),JSON.stringify(report,null,2));await writeFile(join(base,'runtime.log'),log)
}
console.log(JSON.stringify(report,null,2))
