#!/usr/bin/env node
import { spawn } from 'node:child_process'
import { access, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const root = fileURLToPath(new URL('../', import.meta.url))
const directory = resolve(process.env.HUOHUO_INSTANCE_DIR ?? join(root, '.instance/manual'))
let interrupted = false
let active
let killTimer
function stop() {
  interrupted = true
  if (!active?.pid) return
  try { process.kill(process.platform === 'win32' ? active.pid : -active.pid, 'SIGTERM') } catch {}
  const target = active.pid
  killTimer ??= setTimeout(() => {
    try { process.kill(process.platform === 'win32' ? target : -target, 'SIGKILL') } catch {}
  }, 8000)
}
process.on('SIGINT', stop); process.on('SIGTERM', stop)
function run(command, args, capture = false) {
  return new Promise((resolve, reject) => {
    if (interrupted) { reject(new Error('已停止启动')); return }
    const child = spawn(command, args, { cwd: root, detached: process.platform !== 'win32', stdio: ['inherit', capture ? 'pipe' : 'inherit', 'inherit'] })
    active = child
    let output = ''; child.stdout?.on('data', data => { output += data })
    child.once('error', reject)
    child.once('close', (code, signal) => {
      active = undefined
      clearTimeout(killTimer)
      if (interrupted) reject(new Error('已停止；不会继续安装或启动服务'))
      else if (code === 0) resolve(output)
      else reject(new Error(`${command} 退出码 ${code ?? signal}`))
    })
  })
}
try {
  let exists = false
  try { await access(join(directory, 'instance.json')); exists = true } catch {}
  if (!exists) {
    console.log('首次创建你的持久实例；使用真实模型和真实行情，凭据稍后在本机界面填写。')
    await run('npm', ['run', 'build'])
    const packed = JSON.parse(await run('npm', ['pack', '--json'], true))
    await mkdir(dirname(directory), { recursive: true, mode: 0o700 })
    await run(process.execPath, [join(root, 'lib/distribution/cli.js'), 'init', directory, join(root, packed[0].filename)])
  }
  console.log(`实例保存于：${directory}\n此入口不会运行测试模型或合成行情。`)
  // 从实例安装包运行，避免源码修改与已经安装的 Profile 混用。
  const cli = join(directory, 'dsh/profiles/huohuo-worker/node_modules/@huohuo/research-agent/lib/distribution/cli.js')
  try { await access(cli); await access(join(directory, 'worker-install.json')) }
  catch {
    console.log('检测到首次依赖安装未完成；保留身份、配置与数据库，继续安装。')
    await run('npm', ['run', 'build'])
    await run(process.execPath, [join(root, 'lib/distribution/cli.js'), 'repair-install', directory])
  }
  await run(process.execPath, [cli, 'start', directory, ...process.argv.slice(2)])
} catch (error) {
  console.error(error instanceof Error ? error.message : '启动失败'); process.exitCode = interrupted ? 130 : 1
}
