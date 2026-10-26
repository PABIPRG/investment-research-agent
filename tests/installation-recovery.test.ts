import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, mkdir, writeFile, readFile, access, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { spawn } from 'node:child_process'
import { packageRoot } from '../distribution/instance.js'

async function fixture() {
  const temp = await mkdtemp(join(tmpdir(), 'huohuo-install-recovery-'))
  const python = join(temp, 'python')
  // 故障注入只验证初始化顺序和恢复契约；真实安装另在仓外验收。
  await writeFile(python, `#!${process.execPath}\nif(process.argv[2]==='-c') console.log(JSON.stringify({executable:process.argv[1],version:[3,11,0]}));else process.exit(23);\n`, { mode: 0o700 })
  const tarball = join(temp, 'product.tgz'); await writeFile(tarball, 'controlled-package')
  const target = join(temp, 'missing-parent', 'instance')
  const cli = async (...args: string[]) => {
    const child = spawn(process.execPath, [join(packageRoot, 'lib/distribution/cli.js'), ...args], {
      env: { ...process.env, HUOHUO_PYTHON: python }, stdio: ['ignore', 'pipe', 'pipe'],
    })
    let output = ''; child.stdout.on('data', data => { output += data }); child.stderr.on('data', data => { output += data })
    const code = await new Promise<number | null>((resolve, reject) => { child.once('error', reject); child.once('close', resolve) })
    return { code, output }
  }
  return { temp, target, tarball, cli }
}

test('无效端口和缺失发行包在创建实例前失败', async () => {
  const f = await fixture()
  try {
    let result = await f.cli('init', f.target, f.tarball, '0')
    assert.equal(result.code, 1); assert.match(result.output, /端口无效/)
    await assert.rejects(access(f.target), { code: 'ENOENT' })
    result = await f.cli('init', f.target, join(f.temp, 'missing.tgz'), '18720')
    assert.equal(result.code, 1); assert.match(result.output, /发行包/)
    await assert.rejects(access(f.target), { code: 'ENOENT' })
  } finally { await rm(f.temp, { recursive: true, force: true }) }
})

test('Python 准备失败保存原身份和阶段，repair-install 不再误报缺 CLI', async () => {
  const f = await fixture()
  try {
    const first = await f.cli('init', f.target, f.tarball, '18720')
    assert.equal(first.code, 1); assert.match(first.output, /Python.*repair-install/s)
    const original = await readFile(join(f.target, 'instance.json'), 'utf8')
    assert.ok(JSON.parse(original).principal)
    const state = JSON.parse(await readFile(join(f.target, 'initialization.json'), 'utf8'))
    assert.equal(state.status, 'failed'); assert.equal(state.stage, 'python-environment')
    await writeFile(join(f.target, 'business.sqlite3'), 'preserve-database')
    await mkdir(join(f.target, 'dsh/profiles/huohuo-worker'), { recursive: true })
    await writeFile(join(f.target, 'dsh/profiles/huohuo-worker/cordis.patch.yml'), 'user-patch')
    const repeated = await f.cli('init', f.target, f.tarball, '18720')
    assert.equal(repeated.code, 1); assert.match(repeated.output, /已存在/)
    const repair = await f.cli('repair-install', f.target)
    assert.equal(repair.code, 1); assert.match(repair.output, /Python.*repair-install/s)
    assert.doesNotMatch(repair.output, /Cannot find module|CLI 缺失|初始化完成/)
    assert.equal(await readFile(join(f.target, 'instance.json'), 'utf8'), original)
    assert.equal(await readFile(join(f.target, 'business.sqlite3'), 'utf8'), 'preserve-database')
    assert.equal(await readFile(join(f.target, 'dsh/profiles/huohuo-worker/cordis.patch.yml'), 'utf8'), 'user-patch')
  } finally { await rm(f.temp, { recursive: true, force: true }) }
})

for (const failure of ['python-dependencies', 'worker-dependencies']) test(`${failure} 失败后修复完成并保留身份、数据与用户 patch`, async () => {
  const f = await fixture()
  try {
    const phase = join(f.temp, 'failure-phase')
    await writeFile(phase, failure)
    const python = join(f.temp, 'python')
    await writeFile(python, `#!${process.execPath}
const fs=require('node:fs'),path=require('node:path');
if(process.argv[2]==='-c') console.log(JSON.stringify({executable:process.argv[1],version:[3,11,0]}));
else if(process.argv[3]==='venv') {const dest=path.join(process.argv[4],'bin');fs.mkdirSync(dest,{recursive:true});fs.copyFileSync(process.argv[1],path.join(dest,'python'));fs.chmodSync(path.join(dest,'python'),0o700);}
else if(process.argv[3]==='pip' && fs.readFileSync(${JSON.stringify(phase)},'utf8')==='python-dependencies') process.exit(24);
`, { mode: 0o700 })
    const npm = join(f.temp, 'npm')
    await writeFile(npm, `#!${process.execPath}
const fs=require('node:fs'),path=require('node:path');
if(fs.readFileSync(${JSON.stringify(phase)},'utf8')==='worker-dependencies') process.exit(25);
for(const name of ['@huohuo/research-agent/lib/distribution/cli.js','@deepseek-ai/dsh/lib/bin.js']) {const file=path.join(process.cwd(),'node_modules',name);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,'fixture');}
`, { mode: 0o700 })
    const run = async (...args: string[]) => {
      const child = spawn(process.execPath, [join(packageRoot, 'lib/distribution/cli.js'), ...args], {
        env: { ...process.env, HUOHUO_PYTHON: python, PATH: `${f.temp}:${process.env.PATH}` }, stdio: ['ignore', 'pipe', 'pipe'],
      })
      let output = ''; child.stdout.on('data', d => { output += d }); child.stderr.on('data', d => { output += d })
      const code = await new Promise<number | null>((resolve, reject) => { child.once('error', reject); child.once('close', resolve) })
      return { code, output }
    }
    const first = await run('init', f.target, f.tarball, '18720')
    assert.equal(first.code, 1); assert.match(first.output, /安装失败.*repair-install/s)
    assert.doesNotMatch(first.output, /初始化完成|Cannot find module/)
    const original = await readFile(join(f.target, 'instance.json'), 'utf8')
    const state = JSON.parse(await readFile(join(f.target, 'initialization.json'), 'utf8'))
    assert.equal(state.stage, failure); assert.equal(state.status, 'failed')
    const start = await run('start', f.target, '18721', '--no-open')
    assert.equal(start.code, 1); assert.match(start.output, /安装未完成.*repair-install/s)
    await writeFile(join(f.target, 'business.sqlite3'), 'retained-db')
    const patch = join(f.target, 'dsh/profiles/huohuo-worker/cordis.patch.yml')
    await writeFile(patch, 'retained-user-patch')
    await writeFile(phase, '')
    const repaired = await run('repair-install', f.target)
    assert.equal(repaired.code, 0, repaired.output)
    assert.equal(JSON.parse(await readFile(join(f.target, 'initialization.json'), 'utf8')).status, 'complete')
    assert.equal(await readFile(join(f.target, 'instance.json'), 'utf8'), original)
    assert.equal(await readFile(join(f.target, 'business.sqlite3'), 'utf8'), 'retained-db')
    assert.equal(await readFile(patch, 'utf8'), 'retained-user-patch')
    await writeFile(join(f.target, 'product.tgz'), 'changed')
    const changed = await run('repair-install', f.target)
    assert.equal(changed.code, 1); assert.match(changed.output, /校验值已变化/)
    assert.equal(await readFile(join(f.target, 'instance.json'), 'utf8'), original)
  } finally { await rm(f.temp, { recursive: true, force: true }) }
})

test('初始化中断回收自身安装子进程并保留可修复身份', { skip: process.platform === 'win32', timeout: 15_000 }, async () => {
  const f = await fixture()
  const marker = join(f.temp, 'installer-pid')
  const python = join(f.temp, 'python')
  await writeFile(python, `#!${process.execPath}
const fs=require('node:fs');
if(process.argv[2]==='-c') console.log(JSON.stringify({executable:process.argv[1],version:[3,11,0]}));
else {fs.writeFileSync(${JSON.stringify(marker)},String(process.pid));process.on('SIGTERM',()=>{});setInterval(()=>{},1000);}
`, { mode: 0o700 })
  const child = spawn(process.execPath, [join(packageRoot, 'lib/distribution/cli.js'), 'init', f.target, f.tarball, '18720'], {
    env: { ...process.env, HUOHUO_PYTHON: python }, stdio: ['ignore', 'pipe', 'pipe'],
  })
  let output = ''; child.stdout.on('data', d => { output += d }); child.stderr.on('data', d => { output += d })
  const exited = new Promise<number | null>(resolve => child.once('close', resolve))
  try {
    let pid = 0
    for (let i = 0; i < 100 && !pid; i++) {
      try { pid = Number(await readFile(marker, 'utf8')) } catch {}
      if (!pid) await new Promise(resolve => setTimeout(resolve, 30))
    }
    assert.ok(pid, output)
    child.kill('SIGINT')
    assert.equal(await exited, 130, output)
    assert.match(output, /安装已中止/)
    assert.equal(JSON.parse(await readFile(join(f.target, 'initialization.json'), 'utf8')).status, 'failed')
    assert.ok(JSON.parse(await readFile(join(f.target, 'instance.json'), 'utf8')).principal)
    assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' })
    await assert.rejects(access(join(f.target, 'worker-install.json')), { code: 'ENOENT' })
  } finally {
    if (child.exitCode === null && child.signalCode === null) { child.kill('SIGTERM'); await exited }
    await rm(f.temp, { recursive: true, force: true })
  }
})

test('身份已落盘但首份初始化记录缺失时，不能只装 worker 后误报修复完成', async () => {
  const f = await fixture()
  try {
    await f.cli('init', f.target, f.tarball, '18720')
    const identity = await readFile(join(f.target, 'instance.json'), 'utf8')
    await rm(join(f.target, 'initialization.json')) // 精确模拟身份与首份记录之间的中断状态。
    await writeFile(join(f.target, 'business.sqlite3'), 'retained-data')
    await writeFile(join(f.temp, 'npm'), `#!${process.execPath}\nconst fs=require('node:fs'),p=require('node:path');for(const n of ['@huohuo/research-agent/lib/distribution/cli.js','@deepseek-ai/dsh/lib/bin.js']){const f=p.join(process.cwd(),'node_modules',n);fs.mkdirSync(p.dirname(f),{recursive:true});fs.writeFileSync(f,'fixture')}\n`, {mode:0o700})
    const child=spawn(process.execPath,[join(packageRoot,'lib/distribution/cli.js'),'repair-install',f.target],{env:{...process.env,HUOHUO_PYTHON:join(f.temp,'python'),PATH:`${f.temp}:${process.env.PATH}`},stdio:['ignore','pipe','pipe']})
    let output='';child.stdout.on('data',d=>output+=d);child.stderr.on('data',d=>output+=d)
    const code=await new Promise(resolve=>child.once('close',resolve))
    assert.equal(code,1,output);assert.match(output,/Python.*repair-install/s)
    assert.equal(JSON.parse(await readFile(join(f.target,'initialization.json'),'utf8')).stage,'python-environment')
    assert.equal(await readFile(join(f.target,'instance.json'),'utf8'),identity)
    assert.equal(await readFile(join(f.target,'business.sqlite3'),'utf8'),'retained-data')
    await assert.rejects(access(join(f.target,'worker-install.json')),{code:'ENOENT'})
  } finally { await rm(f.temp,{recursive:true,force:true}) }
})

for (const healthy of [true,false]) test(`无初始化记录但 Python 已存在：${healthy?'完整环境不重装':'只补缺失依赖'}，保留身份和用户文件`,async()=>{
  const f=await fixture()
  try {
    await f.cli('init',f.target,f.tarball,'18720'); await rm(join(f.target,'initialization.json'))
    const identity=await readFile(join(f.target,'instance.json'),'utf8');const python=JSON.parse(identity).python
    const calls=join(f.temp,'calls'),ready=join(f.temp,'ready');if(healthy)await writeFile(ready,'ok')
    await mkdir(join(f.target,'python/bin'),{recursive:true})
    await writeFile(python,`#!${process.execPath}
const fs=require('node:fs');fs.appendFileSync(${JSON.stringify(calls)},JSON.stringify(process.argv.slice(2))+'\\n');
if(process.argv[2]==='-c') {if(process.argv[3].includes('importlib.metadata'))process.exit(fs.existsSync(${JSON.stringify(ready)})?0:24);console.log(JSON.stringify({executable:process.argv[1],version:[3,11,0]}));}
else if(process.argv[3]==='pip'&&process.argv[4]==='install')fs.writeFileSync(${JSON.stringify(ready)},'ok');
else if(process.argv[3]==='venv')process.exit(99);
`,{mode:0o700})
    await writeFile(join(f.temp,'npm'),`#!${process.execPath}\nconst fs=require('node:fs'),p=require('node:path');for(const n of ['@huohuo/research-agent/lib/distribution/cli.js','@deepseek-ai/dsh/lib/bin.js']){const f=p.join(process.cwd(),'node_modules',n);fs.mkdirSync(p.dirname(f),{recursive:true});fs.writeFileSync(f,'fixture')}\n`,{mode:0o700})
    const patch=join(f.target,'dsh/profiles/huohuo-worker/cordis.patch.yml');await writeFile(patch,'keep-user-patch')
    const child=spawn(process.execPath,[join(packageRoot,'lib/distribution/cli.js'),'repair-install',f.target],{env:{...process.env,HUOHUO_PYTHON:join(f.temp,'python'),PATH:`${f.temp}:${process.env.PATH}`},stdio:['ignore','pipe','pipe']})
    let output='';child.stdout.on('data',d=>output+=d);child.stderr.on('data',d=>output+=d)
    assert.equal(await new Promise(resolve=>child.once('close',resolve)),0,output)
    const log=await readFile(calls,'utf8');assert.doesNotMatch(log,/"venv"/)
    assert.equal(log.includes('"pip","install"'),!healthy)
    assert.equal(await readFile(join(f.target,'instance.json'),'utf8'),identity);assert.equal(await readFile(patch,'utf8'),'keep-user-patch')
  } finally {await rm(f.temp,{recursive:true,force:true})}
})
