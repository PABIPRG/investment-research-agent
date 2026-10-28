import type { Evidence } from '../model.js'
import { EvidenceCard } from '../shared/EvidenceCard.js'
export function EvidenceView({ row, current }: { row: Evidence; current: boolean }) {
  return (
    <EvidenceCard
      row={row}
      context={current ? '当前结果引用的资料' : '历史资料或尚未被当前结果引用'}
    />
  )
}
