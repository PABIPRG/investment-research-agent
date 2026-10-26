import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { isAbsolute } from 'node:path'

const execute = promisify(execFile)

/**
 * 启动前与实例初始化共享同一选择逻辑；只探测已有解释器，不安装或改变系统配置。
 * @param {{ explicit?: string, candidates?: string[] }} [options]
 */
export async function resolvePython(options = {}) {
  const explicit = options.explicit ?? process.env.HUOHUO_PYTHON
  const candidates = explicit ? [explicit] : options.candidates ?? [
    'python3', '/opt/homebrew/bin/python3', '/usr/local/bin/python3',
    'python3.14', 'python3.13', 'python3.12', 'python3.11',
  ]
  const checked = []
  for (const candidate of [...new Set(candidates)]) {
    try {
      const { stdout } = await execute(candidate, ['-c', 'import json,sys; print(json.dumps({"executable":sys.executable,"version":list(sys.version_info[:3])}))'], { timeout: 5_000 })
      const info = JSON.parse(stdout)
      if (!Array.isArray(info.version) || !isAbsolute(info.executable)) throw new Error('无效解释器响应')
      const version = info.version.join('.')
      if (info.version[0] !== 3 || info.version[1] < 11) { checked.push(`${candidate}: Python ${version}，需要 3.11+`); continue }
      return { executable: info.executable, version, checked }
    } catch { checked.push(`${candidate}: 不存在、无法运行或未在 5 秒内响应`) }
  }
  throw new Error(`没有可用的 Python 3.11+。${explicit ? '已指定 HUOHUO_PYTHON，不会替换你的选择。' : ''}\n${checked.join('\n')}\n可设置 HUOHUO_PYTHON=/兼容解释器的绝对路径 后重试。`)
}
