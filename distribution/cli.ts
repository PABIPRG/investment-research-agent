#!/usr/bin/env node
import { spawn } from 'node:child_process'
import { join, resolve } from 'node:path'
import { once } from 'node:events'
import { setTimeout as delay } from 'node:timers/promises'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { initInstance, repairInstance, readInstance, request, packageRoot, ensureInstalled, type Instance } from './instance.js'
import { workerLoop } from './worker.js'
import { installChat, launchChat, stopChat } from './chat.js'
import type { ChildProcess } from 'node:child_process'

export async function serve(config: Instance, configFile: string, signal?: AbortSignal, onReady?: () => Promise<void>): Promise<void> {
  await ensureInstalled(config)
  const controller = new AbortController()
  const child = spawn(config.python, ['-m', 'huohuo.server', '--config', configFile, '--parent-pipe'], {
    cwd: config.workspace, env: { ...process.env, PYTHONPATH: join(packageRoot, 'sidecar'), PYTHONDONTWRITEBYTECODE: '1' },
    stdio: ['pipe', 'pipe', 'inherit'],
  })
  const exit = new Promise<void>(resolveExit => { child.once('exit', () => resolveExit()); child.once('error', () => resolveExit()) })
  child.once('exit', () => controller.abort())
  child.once('error', () => controller.abort())
  const stop = () => controller.abort()
  process.on('SIGTERM', stop); process.on('SIGINT', stop); signal?.addEventListener('abort', stop)
  try {
    // 必须收到本次子进程的就绪通知，不能把同端口的旧服务误认为启动成功。
    await new Promise<void>((ready, reject) => {
      const timeout = setTimeout(() => reject(new Error('本地实例启动超时')), 5_000)
      const fail = () => { clearTimeout(timeout); reject(new Error('本地实例启动失败')) }
      child.once('exit', fail); child.once('error', fail)
      child.stdout!.once('data', data => {
        clearTimeout(timeout); child.off('exit', fail); child.off('error', fail)
        try { const event = JSON.parse(String(data)); if (event.event !== 'listening' || event.port !== config.port) throw new Error(); ready() }
        catch { reject(new Error('本地实例就绪协议无效')) }
      })
    })
    await request(config, '/health')
    if (controller.signal.aborted) throw new Error('本地实例已经退出')
    console.log(JSON.stringify({ status: 'ready', version: '1.0.0', address: `http://127.0.0.1:${config.port}` }))
    await onReady?.()
    await workerLoop(config, controller.signal)
  } finally {
    controller.abort()
    process.off('SIGTERM', stop); process.off('SIGINT', stop); signal?.removeEventListener('abort', stop)
    child.kill('SIGTERM')
    const kill = setTimeout(() => child.kill('SIGKILL'), 3000)
    await exit.catch(() => {})
    clearTimeout(kill)
  }
}

async function main(): Promise<void> {
  const [command, directory, ...args] = process.argv.slice(2)
  if (!directory) throw new Error('用法：huohuo init <实例目录> <发行tgz> [端口]；serve <实例目录>；submit <实例目录> <请求JSON路径>；get/events/evidence <实例目录> <执行ID>；cancel/retry <实例目录> <执行ID> <版本> <幂等键>')
  if (command === 'init') { await initInstance(directory, args[0], args[1] ? Number(args[1]) : 18386); console.log('实例初始化完成'); return }
  const config = await readInstance(directory)
  if (command === 'repair-install') { await repairInstance(directory); console.log('实例依赖修复完成'); return }
  if (command === 'start' || command === 'chat') {
    await ensureInstalled(config)
    await installChat(config)
    const port = args.find(arg => /^\d+$/.test(arg))
    let chat: ChildProcess | undefined
    if (command === 'start') {
      try {
        await serve(config, join(resolve(directory), 'instance.json'), undefined, async () => {
          chat = await launchChat(config, port ? Number(port) : 18387, args.includes('--no-open'))
          chat.on('exit', () => console.log('DSH 聊天进程已退出；后台继续运行。可用 huohuo chat <实例目录> 重新连接。'))
        })
      } finally { if (chat) await stopChat(chat) }
    } else {
      chat = await launchChat(config, port ? Number(port) : 18387, args.includes('--no-open'))
      const stop = () => { void stopChat(chat!) }
      process.on('SIGINT', stop); process.on('SIGTERM', stop)
      await once(chat, 'exit')
      process.off('SIGINT', stop); process.off('SIGTERM', stop)
      if (chat.exitCode) process.exitCode = chat.exitCode
    }
    return
  }
  if (command === 'serve') return serve(config, join(resolve(directory), 'instance.json'))
  if (command === 'list') { console.log(JSON.stringify(await request(config, '/executions'), null, 2)); return }
  if (command === 'submit') console.log(JSON.stringify(await request(config, '/executions', JSON.parse(await readFile(args[0], 'utf8'))), null, 2))
  else if (['get', 'events', 'evidence'].includes(command)) console.log(JSON.stringify(await request(config, `/executions/${encodeURIComponent(args[0])}${command === 'get' ? '' : '/' + command}`), null, 2))
  else if (command === 'cancel' || command === 'retry') console.log(JSON.stringify(await request(config, `/executions/${encodeURIComponent(args[0])}/${command}`, { expected_revision: Number(args[1]), request_key: args[2] }), null, 2))
  else throw new Error('不支持的命令')
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error instanceof Error ? error.message : '操作失败'); process.exitCode = error?.exitCode ?? 1 })
}
