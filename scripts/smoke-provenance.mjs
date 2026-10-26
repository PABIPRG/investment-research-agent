import {readdir,readFile} from 'node:fs/promises'
import {join} from 'node:path'
import {createHash} from 'node:crypto'
/** 包括运行源码、锁与回放夹具；文档变化不改变运行指纹。 */
export async function smokeFingerprint(root) {
 const files=[]
 async function walk(rel){for(const e of await readdir(join(root,rel),{withFileTypes:true})){
  if(['__pycache__','node_modules','.venv'].includes(e.name))continue
  const p=`${rel}/${e.name}`
  if(e.isSymbolicLink())throw Error('运行源码不能依赖符号链接 '+p)
  if(e.isDirectory())await walk(p);else if(!e.name.endsWith('.pyc')&&!e.name.endsWith('.mjs'))files.push(p)
 }}
 for(const dir of ['distribution','product','runtime','sidecar','tests'])await walk(dir)
 files.push('runtime/python.mjs','package.json','npm-shrinkwrap.json','tsconfig.json','scripts/smoke.mjs','scripts/smoke-provenance.mjs','scripts/build-chat-ui.mjs','scripts/generate-research-tools.mjs','tests/smoke-provenance.test.mjs')
 const hash=createHash('sha256')
 for(const p of [...new Set(files)].sort())hash.update(p+'\0').update(await readFile(join(root,p))).update('\0')
 return hash.digest('hex')
}
export async function archiveIntegrity(path){return 'sha512-'+createHash('sha512').update(await readFile(path)).digest('base64')}
export function validateSmokeResume(owner, instance, fingerprint, integrity) {
 if(owner.instance!==instance||!owner.integrity)throw Error('只能恢复冒烟启动器自己的实例')
 if(!owner.runtime_fingerprint)throw Error('旧冒烟缺少运行源码指纹，不能作为当前源码恢复；请新建验证实例')
 if(owner.runtime_fingerprint!==fingerprint)throw Error('运行源码已变化，拒绝混用新代码和旧 Profile；请新建验证实例')
 if(owner.integrity!==integrity)throw Error('冒烟产物已变化，拒绝恢复；请核对来源')
}
