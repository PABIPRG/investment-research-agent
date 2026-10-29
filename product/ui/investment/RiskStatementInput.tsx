import { useState } from 'react'
import { request, errorText } from '../shared/api.js'
import { FieldGroup } from '../shared/FieldGroup.js'

export function RiskStatementInput({
  tier,
  apply,
}: {
  tier: string
  apply: (answers: Record<string, string>, statement: string) => void
}) {
  const [text, setText] = useState(''),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState('')
  const parse = async () => {
    setBusy(true)
    setNotice('')
    try {
      const result = await request<{
        answers: { qid: string; option: number }[]
        missing: string[]
        warnings: { reason: string }[]
      }>('investment-command', { action: 'risk-parse', tier, text })
      apply(Object.fromEntries(result.answers.map((a) => [a.qid, String(a.option)])), text)
      setNotice(
        `已填入 ${result.answers.length} 个待核对答案，仍需补答 ${result.missing.length} 题。请逐题核对后预览。${result.warnings.length ? '有冲突或否定描述，相关题目留空。' : ''}`,
      )
    } catch (e) {
      setNotice(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <FieldGroup
      title="用自己的话描述"
      hint="可选。这里只生成待核对答案；复杂表述可在聊天中让火火帮助梳理。"
    >
      <label>
        投资期限、可承受亏损和目标
        <textarea value={text} maxLength={4000} onChange={(e) => setText(e.target.value)} />
      </label>
      <button type="button" disabled={busy || !text.trim()} onClick={() => void parse()}>
        {busy ? '正在解析…' : '解析并填入待核对答案'}
      </button>
      {notice && <p role="status">{notice}</p>}
    </FieldGroup>
  )
}
