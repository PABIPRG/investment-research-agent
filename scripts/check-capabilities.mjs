// 从 TypeScript 注册源读取静态名称，检查目录/Skill/包入口，禁止维护第二份运行时名单。
import ts from 'typescript'
import assert from 'node:assert/strict'
import {readFile,readdir} from 'node:fs/promises'
import {resolve,dirname,join} from 'node:path'
import {fileURLToPath} from 'node:url'
const root=fileURLToPath(new URL('../',import.meta.url)),cache=new Map()
async function source(file){
 if(cache.has(file))return cache.get(file)
 const ast=ts.createSourceFile(file,await readFile(file,'utf8'),ts.ScriptTarget.Latest,true),vars=new Map(),imports=new Map()
 for(const s of ast.statements){
  if(ts.isVariableStatement(s))for(const d of s.declarationList.declarations)vars.set(d.name.getText(ast),d.initializer)
  if(ts.isImportDeclaration(s)&&s.importClause?.namedBindings&&ts.isNamedImports(s.importClause.namedBindings))for(const b of s.importClause.namedBindings.elements)imports.set(b.name.text,[resolve(dirname(file),s.moduleSpecifier.text.replace(/\.js$/,'.ts')),b.propertyName?.text||b.name.text])
 }
 const lookup=async name=>{if(vars.has(name))return evaluate(vars.get(name));if(imports.has(name)){const [f,n]=imports.get(name);return (await source(f))(n)}throw Error('无法解析注册名 '+name)}
 const evaluate=async n=>{
  if(ts.isAsExpression(n)||ts.isSatisfiesExpression(n))return evaluate(n.expression)
  if(ts.isStringLiteral(n))return n.text
  if(ts.isIdentifier(n))return lookup(n.text)
  if(ts.isArrayLiteralExpression(n)){const result=[];for(const e of n.elements){if(ts.isSpreadElement(e))result.push(...await evaluate(e.expression));else result.push(await evaluate(e))}return result}
  // 生成契约仅需 name，不执行 schema 或任意表达式。
  if(ts.isObjectLiteralExpression(n)){const name=n.properties.find(p=>ts.isPropertyAssignment(p)&&p.name.getText(ast).replaceAll('"','').replaceAll("'",'')==='name');assert.ok(name,'注册项缺少 name');return {name:await evaluate(name.initializer)}}
  if(ts.isCallExpression(n)&&ts.isPropertyAccessExpression(n.expression)&&n.expression.name.text==='map'&&n.arguments.length===1&&ts.isArrowFunction(n.arguments[0])){
   const f=n.arguments[0];assert.ok(ts.isPropertyAccessExpression(f.body)&&f.body.name.text==='name'&&f.body.expression.getText(ast)===f.parameters[0].name.getText(ast),'只支持注册名映射');return (await evaluate(n.expression.expression)).map(x=>x.name)
  }
  throw Error('注册源出现新的表达式，请同步检查器：'+n.getText(ast))
 }
 cache.set(file,lookup);return lookup
}
const names=await(await source(join(root,'product/chat/tools.ts')))('allowedChatToolNames')
const skills=await(await source(join(root,'product/chat/policy.ts')))('chatSkillNames')
assert.equal(new Set(names).size,names.length,'聊天工具重复注册')
const doc=await readFile(join(root,'docs/Skill与Tool能力目录.md'),'utf8'),catalog=doc.split('## 4.')[0]
const documented=new Set([...catalog.split('\n').filter(line=>line.startsWith('|')).join('\n').matchAll(/`([a-z][a-z0-9_]+)`/g)].map(m=>m[1]));documented.delete('read_security_snapshot')
assert.deepEqual([...documented].sort(),[...names].sort(),'工具表遗漏或保留了已删除名称')
for(const name of [...names,...skills])assert.ok(catalog.includes('`'+name+'`'),'目录缺少 '+name)
assert.ok(catalog.includes(`聊天 ${names.length} 个`),'工具数量漂移')
assert.ok(catalog.includes(`聊天 ${skills.length} 个`),'Skill 数量漂移')
const found=[]
for(const dir of await readdir(join(root,'product/skills/chat'))){const content=await readFile(join(root,'product/skills/chat',dir,'SKILL.md'),'utf8');const name=/^name:\s*(.+)$/m.exec(content)?.[1];assert.ok(name,'Skill 缺少名称 '+dir);found.push(name)}
assert.deepEqual(found.sort(),[...skills].sort(),'Skill 文件与允许名单不一致')
for(const path of ['README.md','docs/阅读入口.md','docs/开发指引.md'])assert.ok((await readFile(join(root,path),'utf8')).includes('Skill与Tool能力目录.md'),'缺少目录入口 '+path)
const pkg=JSON.parse(await readFile(join(root,'package.json'),'utf8'));assert.ok(pkg.files.includes('docs/Skill与Tool能力目录.md'),'发行包遗漏目录')
console.log(`能力注册检查通过：${skills.length} 个聊天 Skill，${names.length} 个聊天 Tool；文件、允许名单与文档入口一致。`)
