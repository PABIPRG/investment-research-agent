import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { npmCommand } from '../runtime/npm.mjs'

const execute = promisify(execFile)
const npm = npmCommand()
const root = fileURLToPath(new URL('../', import.meta.url))
const output = resolve(process.argv[2] ?? join(root, 'artifacts/release'))
await mkdir(output, { recursive: true })
const manifest = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'))
if (manifest.private !== true) throw new Error('本次仅生成私有验证产物，private 必须保持 true')
const { stdout } = await execute(npm.command, [...npm.prefix, 'pack', '--json', '--ignore-scripts', '--pack-destination', output, '--cache', join(root, 'artifacts/npm-cache')], { cwd: root, maxBuffer: 8 * 1024 * 1024 })
const [packed] = JSON.parse(stdout)
const paths = new Set(packed.files.map(file => file.path))
const forbidden = /(^|\/)(?:node_modules|tests?|fixtures?|artifacts|__pycache__|\.instance|\.venv|\.git|\.cache)(\/|$)|(?:^|\/)(?:instance|credentials|secrets)\.json$|(?:^|\/)\.env(?:\.|$)|\.(?:pyc|sqlite3?|db|tgz|pem|key)$/i
const bad = [...paths].filter(path => forbidden.test(path))
if (bad.length) throw new Error(`产物含禁止内容：${bad.join(', ')}`)
const required = ['lib/distribution/cli.js', 'lib/distribution/instance.js', 'lib/distribution/worker.js', 'lib/distribution/chat.js', 'lib/runtime/python.mjs', 'lib/product/tools/index.js',
  'lib/product/chat/tools.js', 'lib/product/ui/host.js', 'product/bundle/cordis.patch.yml', 'product/bundle/chat.patch.yml',
  'product/skills/chat/research-chat/SKILL.md', 'ui/client.js', 'ui/host.js', 'ui/package.json',
  'docs/Skill与Tool能力目录.md', 'docs/聊天业务操作实施计划.md', 'docs/聊天业务操作验收.md', 'npm-shrinkwrap.json', 'sidecar/requirements.lock', 'sidecar/requirements.txt', 'third-party/DSH-LICENSE']
async function sourceFiles(directory) {
  const result = []
  for (const entry of await readdir(join(root, directory), { withFileTypes: true })) {
    if (entry.name === '__pycache__' || entry.name === '.npmignore' || entry.name.endsWith('.pyc')) continue
    const path = `${directory}/${entry.name}`
    if (entry.isSymbolicLink()) throw new Error(`源码目录不能依赖符号链接：${path}`)
    if (entry.isDirectory()) result.push(...await sourceFiles(path)); else result.push(path)
  }
  return result
}
for (const directory of ['sidecar/huohuo', 'product/bundle', 'product/skills', 'product/ui/assets']) required.push(...await sourceFiles(directory))
const missing = [...new Set(required)].filter(path => !paths.has(path))
if (missing.length) throw new Error(`产物缺少文件：${missing.join(', ')}`)
const tarball = join(output, packed.filename)
const digest = createHash('sha256').update(await readFile(tarball)).digest('hex')
// Windows 的 tar 按控制台代码页转码文件名；保持 UTF-8 locale 才能与 npm 清单比对。
const tarEnv = process.platform === 'win32' ? { ...process.env, LANG: 'zh_CN.UTF-8', LC_ALL: 'zh_CN.UTF-8' } : process.env
const { stdout: listing } = await execute('tar', ['-tzf', packed.filename], { cwd: output, env: tarEnv, maxBuffer: 8 * 1024 * 1024 })
const actual = listing.trim().split(/\r?\n/).map(path => path.replace(/^package\//, '')).filter(path => path && !path.endsWith('/'))
if (actual.length !== paths.size || actual.some(path => !paths.has(path))) throw new Error('tgz 实际清单与 npm 返回清单不一致')
const lock = JSON.parse(await readFile(join(root, 'npm-shrinkwrap.json'), 'utf8'))
if (lock.name !== manifest.name || lock.version !== manifest.version) throw new Error('发行锁与包身份不一致')
for (const [name, spec] of Object.entries(manifest.dependencies)) {
  if (/^(?:workspace:|file:|link:|\/)/.test(spec)) throw new Error(`运行依赖不是独立 registry 版本：${name}`)
}
await writeFile(join(output, 'package-report.json'), JSON.stringify({
  name: manifest.name, version: manifest.version, private: manifest.private, tarball, sha256: digest,
  file_count: paths.size, required_checked: new Set(required).size, forbidden_count: 0,
  files: packed.files, source_files: await Promise.all([...new Set(required)].map(async path => ({ path,
    sha256: createHash('sha256').update(await readFile(join(root, path))).digest('hex') }))),
}, null, 2) + '\n')
await writeFile(tarball + '.sha256', `${digest}  ${packed.filename}\n`)
console.log(JSON.stringify({ tarball, sha256: digest, files: paths.size, status: 'passed' }, null, 2))
