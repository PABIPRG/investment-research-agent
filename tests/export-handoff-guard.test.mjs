import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,writeFile,mkdir,rm,symlink} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createHash} from 'node:crypto'
import {assertPristineExport} from '../scripts/export-handoff-guard.mjs'
for(const mutation of ['git','modified','unknown','symlink'])test('导出覆盖保护 '+mutation,async()=>{
 const base=await mkdtemp(join(tmpdir(),'handoff-guard-'));const root=join(base,'export');await mkdir(root)
 await writeFile(join(root,'README.md'),'original')
 await writeFile(join(root,'SOURCE-MANIFEST.json'),JSON.stringify({files:[{path:'README.md',sha256:createHash('sha256').update('original').digest('hex')}]}))
 try{
  await assertPristineExport(root)
  if(mutation==='git')await mkdir(join(root,'.git'))
  if(mutation==='modified')await writeFile(join(root,'README.md'),'coworker edit')
  if(mutation==='unknown')await writeFile(join(root,'new-file.txt'),'coworker file')
  if(mutation==='symlink')await symlink(root,join(base,'link'))
  await assert.rejects(assertPristineExport(mutation==='symlink'?join(base,'link'):root),/拒绝/)
 }finally{await rm(base,{recursive:true})}
})
