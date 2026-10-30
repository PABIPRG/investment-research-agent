import { useLayoutEffect, useRef, useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import css from './ExpandableText.module.css'
/** Bounded preview; the original text remains available without changing business state. */
export function ExpandableText({
  text,
  label,
  lines = 2,
  tone = 'body',
}: {
  text: string
  label: string
  lines?: 1 | 2
  tone?: 'body' | 'muted' | 'strong'
}) {
  const preview = useRef<HTMLSpanElement>(null)
  const [clipped, setClipped] = useState(false),
    [open, setOpen] = useState(false)
  useLayoutEffect(() => {
    const element = preview.current
    if (!element) return
    const measure = () =>
      setClipped(
        element.clientHeight > 0 &&
          (element.scrollHeight > element.clientHeight + 1 ||
            element.scrollWidth > element.clientWidth + 1),
      )
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    measure()
    return () => observer.disconnect()
  }, [text, lines])
  return (
    <>
      <span className={css.root} data-tone={tone} data-expandable-text={label}>
        <span
          ref={preview}
          className={css.preview}
          data-lines={lines}
          title={clipped ? text : undefined}
        >
          {text}
        </span>
        {clipped && (
          <button
            type="button"
            className={css.reveal}
            aria-label={`查看完整${label}`}
            aria-haspopup="dialog"
            onClick={() => setOpen(true)}
          >
            查看全文
          </button>
        )}
      </span>
      {open && (
        <DetailPanel compact title={`完整${label}`} close={() => setOpen(false)}>
          <p className={css.fullText}>{text}</p>
        </DetailPanel>
      )}
    </>
  )
}
