import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'

/**
 * Windows 上 npm 是 .cmd，Node 的 spawn/execFile 不能直接执行它。
 * 优先用当前 Node 自带的 npm-cli.js，避免经过 cmd.exe 的引号转义。
 * @returns {{ command: string, prefix: string[] }}
 */
export function npmCommand() {
  if (process.platform !== 'win32') return { command: 'npm', prefix: [] }
  const cli = join(dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js')
  if (existsSync(cli)) return { command: process.execPath, prefix: [cli] }
  return { command: process.env.ComSpec ?? 'cmd.exe', prefix: ['/d', '/s', '/c', 'npm'] }
}
