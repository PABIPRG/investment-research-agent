// Explicit local upgrade. Refuse while the instance is running; preserve user data.
import { spawn } from 'node:child_process'
import { copyFile, access } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join, resolve } from 'node:path'
const root = fileURLToPath(new URL('../', import.meta.url))
const directory = resolve(process.env.HUOHUO_INSTANCE_DIR ?? join(root, '.instance/manual'))
const run = (args, capture = false) => new Promise((done, fail) => {
  const child = spawn('npm', args, { cwd: root, stdio: ['inherit', capture ? 'pipe' : 'inherit', 'inherit'] })
  let output = ''; child.stdout?.on('data', data => { output += data })
  child.once('error', fail); child.once('exit', code => code === 0 ? done(output) : fail(new Error(`npm 退出码 ${code}`)))
})
await run(['run', 'build'])
const { readInstance, installWorker } = await import('../lib/distribution/instance.js')
const { installChat, checkChatPort, validateChatUpgrade } = await import('../lib/distribution/chat.js')
const { validateStrategyUpgrade } = await import('../lib/distribution/strategy-profile.js')
const config = await readInstance(directory)
await checkChatPort(config.port)
await checkChatPort(Number(process.env.HUOHUO_WEB_PORT ?? 18387))
await validateChatUpgrade(config)
await validateStrategyUpgrade(config)
const [{ filename }] = JSON.parse(await run(['pack', '--json'], true))
const previous = join(directory, 'product.before-chat-shell.tgz')
try { await access(previous) } catch { await copyFile(join(directory, 'product.tgz'), previous) }
await copyFile(join(root, filename), join(directory, 'product.tgz'))
await installWorker(config, true)
await installChat(config, true)
console.log('火火实例已更新；身份、数据库、会话和用户模型配置已保留。运行 npm start 打开。')
