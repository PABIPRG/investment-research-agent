import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, writeFile, readFile, access } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import { packageRoot } from '../distribution/instance.js'

test('首次构建中止会回收不响应 TERM 的子进程，且不继续安装', { skip: process.platform === 'win32', timeout: 20_000 }, async () => {
  const temp = await mkdtemp(join(tmpdir(), 'huohuo-start-stop-'))
  await writeFile(join(temp, 'npm'), '#!/bin/sh\ntrap "" TERM\nprintf "%s\\n" "$*" >> "$HUOHUO_TEST_MARKER"\nwhile :; do /bin/sleep 1; done\n', { mode: 0o700 })
  const marker = join(temp, 'commands')
  const child = spawn(process.execPath, [join(packageRoot, 'scripts/start.mjs')], { env: { ...process.env, PATH: temp,
    HUOHUO_TEST_MARKER: marker, HUOHUO_INSTANCE_DIR: join(temp, 'instance') }, stdio: ['ignore', 'pipe', 'pipe'] })
  let output = ''; child.stdout?.on('data', d => { output += d }); child.stderr?.on('data', d => { output += d })
  const exit = new Promise<number | null>(r => child.once('exit', code => r(code)))
  try {
    for (let i = 0; i < 250; i++) { try { await access(marker); break } catch {} if (child.exitCode !== null) break; await delay(20) }
    try { await access(marker) } catch { assert.fail('测试命令未启动：' + output) }
    child.kill('SIGINT')
    assert.equal(await exit, 130)
    assert.equal((await readFile(marker, 'utf8')).trim(), 'run build')
    await assert.rejects(() => access(join(temp, 'instance')))
  } finally { if (child.exitCode === null) { child.kill('SIGINT'); await exit } }
})
