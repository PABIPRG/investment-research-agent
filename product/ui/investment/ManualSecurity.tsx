import { useState } from 'react'
import type { Security } from './types.js'
export function ManualSecurity({
  select,
  disabled,
}: {
  select: (security: Security) => void
  disabled: boolean
}) {
  const [code, setCode] = useState(''),
    [name, setName] = useState('')
  const valid =
    /^(?:(?:600|601|603|605|688|689|000|001|002|003|300|301)\d{3}|5[01268]\d{4}|159\d{3})$/.test(
      code,
    )
  return (
    <details>
      <summary>没有搜索到？填写股票或场内基金</summary>
      <div>
        <p>按你提供的名称和代码记录，未经过交易所名录核验；保存前请与券商记录核对。</p>
        <label>
          证券名称
          <input
            disabled={disabled}
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="填写完整名称"
          />
        </label>
        <label>
          六位证券代码
          <input
            disabled={disabled}
            inputMode="numeric"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="例如 513130"
          />
        </label>
        <button
          type="button"
          disabled={disabled || !valid || !name.trim()}
          onClick={() => select({ code, name: name.trim() })}
        >
          使用此证券记录
        </button>
      </div>
    </details>
  )
}
