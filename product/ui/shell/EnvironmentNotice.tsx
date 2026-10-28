import { useEffect, useState } from 'react'
import css from './Root.module.css'
export function EnvironmentNotice() {
  const [controlled, setControlled] = useState(false)
  useEffect(() => {
    const abort = new AbortController()
    fetch('api/huohuo/environment', { signal: abort.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setControlled(data?.controlled === true))
      .catch(() => {})
    return () => abort.abort()
  }, [])
  return controlled ? (
    <aside className={css.environment} aria-label="预览环境说明">
      <strong>交互预览 · 未连接真实模型</strong>
      <p>
        这里可查看界面和已有合成记录；普通提问不会执行研究。自由对话需使用已配置模型的正常产品实例。
      </p>
    </aside>
  ) : null
}
