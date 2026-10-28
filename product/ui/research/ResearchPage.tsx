import { useState } from 'react'
import { MandatesPage } from '../Mandates.js'
import css from './ResearchPage.module.css'
import { QueryPage } from './QueryPage.js'
export function ResearchPage({ goChat }: { goChat: () => void }) {
  const [view, setView] = useState<'ongoing' | 'once'>('ongoing')
  const switcher = (
    <nav className={css.views} aria-label="研究记录类型">
      <button aria-pressed={view === 'ongoing'} onClick={() => setView('ongoing')}>
        持续跟进
      </button>
      <button aria-pressed={view === 'once'} onClick={() => setView('once')}>
        一次性研究
      </button>
    </nav>
  )
  return view === 'once' ? (
    <QueryPage goChat={goChat} switcher={switcher} />
  ) : (
    <MandatesPage goChat={goChat} switcher={switcher} />
  )
}
