import { useLayoutEffect, type RefObject } from 'react'

/** Add presentation/accessibility hints; DSH still owns questions and answer handling. */
export function useQuestionShortcut(root: RefObject<HTMLDivElement>) {
  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    const selector = '[data-question-key] .Mbwy4a_footerActions > button:last-child'
    const headings = '[data-question-key] .Mbwy4a_headingBlock'
    const update = () => {
      for (const heading of el.querySelectorAll<HTMLElement>(headings)) {
        heading.tabIndex = 0
        heading.setAttribute('role', 'region')
        heading.setAttribute('aria-label', '问题全文')
      }
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
      for (const heading of el.querySelectorAll<HTMLElement>(headings)) {
        heading.removeAttribute('tabindex')
        heading.removeAttribute('role')
        heading.removeAttribute('aria-label')
      }
      for (const button of el.querySelectorAll<HTMLButtonElement>(
        '[data-huohuo-question-submit]',
      )) {
        delete button.dataset.huohuoQuestionSubmit
        button.removeAttribute('aria-keyshortcuts')
      }
    }
  }, [root])
}
