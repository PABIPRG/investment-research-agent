import css from '../Query.module.css'
const brandPath = 'api/huohuo/brand.png'
export function BrandMark({ size = 32 }: { size?: number }) {
  return <img src={brandPath} width={size} height={size} className={css.brandMark} alt="火火" />
}
export function BrandName() {
  return (
    <span className={css.brandName}>
      <strong>火火</strong>
      <small>投研伙伴 · 1.0.0</small>
    </span>
  )
}
export function QueryIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      aria-hidden="true"
    >
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </svg>
  )
}

/** Product-owned metadata adaptation for rc2's fixed document-title presenter. */
export function brandMetadata() {
  const originalTitle = document.title
  const icons = [
    ...document.querySelectorAll<HTMLLinkElement>(
      'link[rel="icon"], link[rel="shortcut icon"], link[rel="apple-touch-icon"]',
    ),
  ]
  const previous = icons.map((link) => ({
    link,
    href: link.getAttribute('href'),
    type: link.getAttribute('type'),
  }))
  for (const link of icons) {
    link.href = brandPath
    link.type = 'image/png'
  }
  const rewrite = () => {
    const next = document.title.replace(/(^| — )DeepSeek Harness$/, '$1火火')
    if (next !== document.title) document.title = next
  }
  rewrite()
  const observer = new MutationObserver(rewrite)
  observer.observe(document.head, { subtree: true, childList: true, characterData: true })
  return () => {
    observer.disconnect()
    document.title = originalTitle
    for (const { link, href, type } of previous) {
      if (href === null) link.removeAttribute('href')
      else link.setAttribute('href', href)
      if (type === null) link.removeAttribute('type')
      else link.setAttribute('type', type)
    }
  }
}
