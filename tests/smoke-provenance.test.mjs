import test from 'node:test'
import assert from 'node:assert/strict'
import {validateSmokeResume} from '../scripts/smoke-provenance.mjs'
const owner={instance:'/owned/instance',integrity:'sha512-original',runtime_fingerprint:'same-runtime'}
test('恢复仅接受同一运行源码与原产物',()=>{
 assert.doesNotThrow(()=>validateSmokeResume(owner,owner.instance,'same-runtime','sha512-original'))
 assert.throws(()=>validateSmokeResume(owner,owner.instance,'changed-runtime','sha512-original'),/源码/)
 assert.throws(()=>validateSmokeResume(owner,owner.instance,'same-runtime','sha512-tampered'),/产物/)
 assert.throws(()=>validateSmokeResume({...owner,runtime_fingerprint:undefined},owner.instance,'same-runtime','sha512-original'),/指纹/)
})

test('运行指纹覆盖代码与锁，文档不影响恢复',async()=>{
 const {mkdtemp,mkdir,writeFile,rm}=await import('node:fs/promises');const {tmpdir}=await import('node:os');const {join}=await import('node:path');const {smokeFingerprint}=await import('../scripts/smoke-provenance.mjs')
 const root=await mkdtemp(join(tmpdir(),'smoke-fingerprint-'))
 try{
  for(const dir of ['distribution','product','runtime','sidecar','tests','scripts','docs'])await mkdir(join(root,dir))
  for(const file of ['runtime/python.mjs','package.json','npm-shrinkwrap.json','tsconfig.json','scripts/smoke.mjs','scripts/smoke-provenance.mjs','scripts/build-chat-ui.mjs','scripts/generate-research-tools.mjs','tests/smoke-provenance.test.mjs'])await writeFile(join(root,file),'baseline')
  await writeFile(join(root,'distribution/worker.ts'),'original')
  const before=await smokeFingerprint(root);await writeFile(join(root,'docs/guide.md'),'new guide');assert.equal(await smokeFingerprint(root),before)
  await writeFile(join(root,'distribution/worker.ts'),'changed');assert.notEqual(await smokeFingerprint(root),before)
 }finally{await rm(root,{recursive:true})}
})
