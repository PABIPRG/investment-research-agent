import { useLayoutEffect, type RefObject } from 'react'

/** Decorate the native submit action; DSH continues to own keyboard and answer handling. */
export function useQuestionShortcut(root: RefObject<HTMLDivElement>) {
  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    const selector = '[data-question-key] .Mbwy4a_footerActions > button:last-child'
    const update = () => {
      for (const button of el.querySelectorAll<HTMLButtonElement>(selector)) {
        const submit = ['提交', 'Submit'].includes(button.textContent?.trim() ?? '')
        if (submit) {
          if (button.dataset.huohuoQuestionSubmit !== 'true')
            button.dataset.huohuoQuestionSubmit = 'true'
          if (button.getAttribute('aria-keyshortcuts') !== 'Enter')
            button.setAttribute('aria-keyshortcuts', 'Enter')
        } else if (button.dataset.huohuoQuestionSubmit) {
          delete button.dataset.huohuoQuestionSubmit
          button.removeAttribute('aria-keyshortcuts')
        }
      }
    }
    const observer = new MutationObserver(update)
    observer.observe(el, { childList: true, subtree: true, characterData: true })
    update()
    return () => {
      observer.disconnect()
      for (const button of el.querySelectorAll<HTMLButtonElement>(
        '[data-huohuo-question-submit]',
      )) {
        delete button.dataset.huohuoQuestionSubmit
        button.removeAttribute('aria-keyshortcuts')
      }
    }
  }, [root])
}
