// 精选产品源码导出。构建与实例永远不参与遍历；归档时间固定，可重复产生同一 SHA。
import {mkdir,readdir,readFile,writeFile,copyFile,rm,lstat} from 'node:fs/promises'
import {join,resolve,dirname} from 'node:path'
import {fileURLToPath} from 'node:url'
import {createHash} from 'node:crypto'
import {execFile} from 'node:child_process'
import {promisify} from 'node:util'
import {assertPristineExport} from './export-handoff-guard.mjs'
import {resolvePython} from '../runtime/python.mjs'
const run=promisify(execFile),root=fileURLToPath(new URL('../',import.meta.url))
const out=join(root,'artifacts/handoff'),dest=join(out,'investment-research-agent')
const roots=['distribution','product','runtime','sidecar','tests','third-party']
const files=['.gitignore','AGENTS.md','README.md','package.json','npm-shrinkwrap.json','tsconfig.json',
 'scripts/build-chat-ui.mjs','scripts/generate-research-tools.mjs','scripts/start.mjs','scripts/update-instance.mjs','scripts/smoke.mjs','scripts/smoke-provenance.mjs','scripts/smoke-skills.mjs','scripts/uat-skills.mjs','scripts/package-release.mjs','scripts/export-handoff.mjs','scripts/export-handoff-guard.mjs','scripts/render-architecture.py','scripts/verify-release.mjs',
 'docs/阅读入口.md','docs/当前架构与装配.md','docs/启动指引.md','docs/开发指引.md','docs/交付与验收.md']
const forbidden=/(^|\/)(?:node_modules|lib|artifacts|__pycache__|\.git|\.venv|\.instance|\.cache)(\/|$)|(?:^|\/)(?:instance|credentials|secrets)\.json$|(?:^|\/)\.env(?:\.|$)|\.(?:pyc|sqlite3?|db|tgz|pem|key)$/i
async function walk(rel){for(const item of await readdir(join(root,rel),{withFileTypes:true})){
 const path=`${rel}/${item.name}`
 if(forbidden.test(path))continue
 if(item.isSymbolicLink())throw Error('不能导出符号链接 '+path)
 // 三个仅绑定历史实例的运行脚本保留在本地，不进入新仓。
 if(['tests/final-package-startup.mjs','tests/worker-finish-runtime.mjs','tests/night-research-runtime.mjs'].includes(path))continue
 if(item.isDirectory())await walk(path);else files.push(path)
}}
for(const dir of [...roots,'docs/architecture'])await walk(dir)
const manifest=[]
for(const path of [...new Set(files)].sort()){
 if(forbidden.test(path))throw Error('禁止路径 '+path)
 const data=await readFile(join(root,path))
 if(/\.(?:md|ts|tsx|mjs|py|json|yml|mmd|svg)$/.test(path)&&/\/Users\/[^/\s]+\/|Date\.parse\(['"]20[0-9]{2}-/.test(data.toString()))throw Error('开发者路径或历史截止泄漏 '+path)
 manifest.push({path,sha256:createHash('sha256').update(data).digest('hex'),bytes:data.length})
}
await mkdir(out,{recursive:true})
let exists=true;try{await lstat(dest)}catch(e){if(e.code!=='ENOENT')throw e;exists=false}
if(exists){await assertPristineExport(dest);await rm(dest,{recursive:true})}
await mkdir(dest)
for(const {path} of manifest){await mkdir(dirname(join(dest,path)),{recursive:true});await copyFile(join(root,path),join(dest,path))}
await writeFile(join(dest,'SOURCE-MANIFEST.json'),JSON.stringify({format:1,product:'investment-research-agent',history:'independent root intended; no .git exported',files:manifest},null,2)+'\n')
const archive=join(out,'investment-research-agent-source.zip'),python=await resolvePython()
await run(python.executable,['-c',`import zipfile,pathlib,sys
root=pathlib.Path(sys.argv[1])
with zipfile.ZipFile(sys.argv[2],'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(root.rglob('*')):
  if p.is_file():
   i=zipfile.ZipInfo(p.relative_to(root).as_posix(),(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,p.read_bytes())`,dest,archive])
const sha256=createHash('sha256').update(await readFile(archive)).digest('hex')
await writeFile(archive+'.sha256',`${sha256}  investment-research-agent-source.zip\n`)
await writeFile(join(out,'handoff-report.json'),JSON.stringify({source_root:root,export_root:dest,archive,sha256,files:manifest.length+1,excluded:['historical docs with developer paths','historical runtime scripts','instances and secrets','dependencies and caches','build outputs','artifacts','.git'],files_manifest:manifest},null,2)+'\n')
console.log(JSON.stringify({archive,sha256,files:manifest.length+1},null,2))
