import { useState } from 'react'
import css from './HeaderMark.module.css'

/** 独立的半脸构图，保留两只手与镜片；不把应用头像强行裁成顶部栏图标。 */
export function HeaderMark() {
  const [failed, setFailed] = useState(false)
  return (
    <span className={css.frame} aria-hidden="true" data-huohuo-header-mark="peek">
      <img
        className={`${css.image} ${failed ? css.fallback : ''}`}
        src={`api/huohuo/companion/${failed ? 'fallback.png' : 'header-peek.png'}`}
        alt=""
        onError={failed ? undefined : () => setFailed(true)}
        draggable={false}
      />
    </span>
  )
}
