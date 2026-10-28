import { EvidenceCard } from '../shared/EvidenceCard.js'
import css from '../Query.module.css'
import type { MandateView } from './model.js'
export function MandateEvidence({ current }: { current: MandateView }) {
  return (
    <section aria-label="留存资料">
      {!current.evidence.length && (
        <p className={css.note}>尚无留存资料；采集失败不会算作研究成功。</p>
      )}
      {current.evidence.map((row) => (
        <EvidenceCard key={row.evidence_id} row={row} />
      ))}
    </section>
  )
}
