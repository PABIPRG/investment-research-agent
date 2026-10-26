import {readFile,readdir,lstat} from 'node:fs/promises'
import {join,posix} from 'node:path'
import {createHash} from 'node:crypto'
/** 只覆盖完全未动过的本工具导出。包括构建缓存在内的未知内容一律拒绝。 */
export async function assertPristineExport(root){
 if((await lstat(root)).isSymbolicLink())throw Error('拒绝覆盖符号链接导出目录')
 let manifest;try{manifest=JSON.parse(await readFile(join(root,'SOURCE-MANIFEST.json'),'utf8'))}catch{throw Error('拒绝覆盖：目录没有有效的来源清单')}
 if(!Array.isArray(manifest.files))throw Error('拒绝覆盖：清单无效')
 const expected=new Map(),directories=new Set()
 for(const f of manifest.files){
  if(typeof f.path!=='string'||f.path.startsWith('/')||f.path.split('/').some(p=>['..','.git',''].includes(p))||expected.has(f.path))throw Error('拒绝覆盖：清单路径无效')
  expected.set(f.path,f.sha256)
  let d=posix.dirname(f.path);while(d!=='.'){directories.add(d);d=posix.dirname(d)}
 }
 const found=new Set()
 async function walk(rel=''){
  for(const e of await readdir(join(root,rel),{withFileTypes:true})){
   const p=rel?`${rel}/${e.name}`:e.name
   if(e.name==='.git'||e.isSymbolicLink())throw Error('拒绝覆盖：含 Git 或符号链接 '+p)
   if(e.isDirectory()){if(!directories.has(p))throw Error('拒绝覆盖：未知目录（含缓存） '+p);await walk(p)}
   else if(p!=='SOURCE-MANIFEST.json'){
    if(!expected.has(p))throw Error('拒绝覆盖：未知文件 '+p)
    if(createHash('sha256').update(await readFile(join(root,p))).digest('hex')!==expected.get(p))throw Error('拒绝覆盖：源码已修改 '+p)
    found.add(p)
   }
  }
 }
 await walk();if(found.size!==expected.size)throw Error('拒绝覆盖：源码文件已删除')
}
