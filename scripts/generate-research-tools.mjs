import { spawnSync } from 'node:child_process'
import { readFile, writeFile } from 'node:fs/promises'
import { resolvePython } from '../runtime/python.mjs'
const python = await resolvePython()
const result = spawnSync(python.executable, ['-c', 'import json,runpy; m=runpy.run_path("sidecar/huohuo/research_entities/tool_contracts.py"); print(json.dumps(m["catalog"](),ensure_ascii=False,sort_keys=True,indent=2))'], {
  cwd: new URL('../', import.meta.url), env: { ...process.env, PYTHONPATH: 'sidecar' }, encoding: 'utf8',
})
if (result.status !== 0) throw new Error(result.stderr)
const data = JSON.parse(result.stdout)
if (new Set(data.map(x=>x.name)).size !== data.length) throw new Error('重复工具名')
const output = '// 自动生成；请修改 Python tool_contracts.py 后运行 npm run tools:generate。\nexport const researchToolCatalog = '+JSON.stringify(data,null,2)+'\n'
const path = new URL('../product/tools/research-tools.generated.ts', import.meta.url)
if (process.argv.includes('--check')) {
  if (await readFile(path,'utf8') !== output) throw new Error('工具定义已过期，请运行 npm run tools:generate')
} else await writeFile(path,output)
console.log(`已${process.argv.includes('--check')?'核对':'生成'} ${data.length} 个 DSH 工具定义`)
