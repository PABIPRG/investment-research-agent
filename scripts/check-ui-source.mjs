import { readdir, readFile } from 'node:fs/promises'
import { resolve, relative } from 'node:path'
import * as prettier from 'prettier'
const root = resolve('product/ui'),
  config = JSON.parse(await readFile('.prettierrc.json', 'utf8'))
let count = 0,
  max = { lines: 0, file: '' },
  failed = false
async function walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = resolve(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name !== 'vendor') await walk(path)
      continue
    }
    if (!/\.(?:ts|tsx|css|js)$/.test(entry.name)) continue
    const source = await readFile(path, 'utf8'),
      lines = source.trimEnd().split('\n').length
    count++
    if (lines > max.lines) max = { lines, file: relative(process.cwd(), path) }
    if (lines > 300) {
      console.error(`超过 300 行：${relative(process.cwd(), path)} (${lines})`)
      failed = true
    }
    if (!(await prettier.check(source, { ...config, filepath: path }))) {
      console.error(`需要格式化：${relative(process.cwd(), path)}`)
      failed = true
    }
  }
}
await walk(root)
console.log(
  `已检查 ${count} 个手写 UI 文件；最长 ${max.lines} 行：${max.file}。仅 vendor 第三方源码排除。`,
)
if (failed) process.exitCode = 1
