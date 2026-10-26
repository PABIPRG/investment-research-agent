import { build } from 'esbuild'
import { mkdir, writeFile, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
const root = fileURLToPath(new URL('../', import.meta.url))
// React remains the official shell singleton. Only our own code/CSS is bundled.
const result = await build({ absWorkingDir: root, entryPoints: ['product/ui/client.tsx'], bundle: true,
  format: 'cjs', platform: 'browser', target: 'es2022', jsx: 'automatic', external: ['react', 'react/jsx-runtime'],
  outfile: 'ui/client.js', write: false, loader: { '.module.css': 'local-css' }, legalComments: 'inline' })
const js = result.outputFiles.find(file => file.path.endsWith('.js')).text
const css = result.outputFiles.find(file => file.path.endsWith('.css'))?.text ?? ''
await mkdir(join(root, 'ui'), { recursive: true })
await writeFile(join(root, 'ui/client.js'), `window.__ModuleLoader__.load({id:"@huohuo/chat-ui",factory(require){const module={exports:{}};const exports=module.exports;const __HUOHUO_CSS__=${JSON.stringify(css)};\n${js}\nreturn module.exports;}});\n`)
await writeFile(join(root, 'ui/host.js'), 'export { apply, inject } from "@huohuo/research-agent/ui-host";\n')
await writeFile(join(root, 'ui/package.json'), await readFile(join(root, 'product/ui/package.json')))
console.log('已构建火火客户端插件（使用 DSH 共享 React）')
