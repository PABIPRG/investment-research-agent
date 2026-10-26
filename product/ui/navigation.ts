import type {DshUiContext} from './dsh-face.js'
const views:Record<string,string|null>={chat:null,mandates:'huohuo-research',investment:'huohuo-investment',notifications:'huohuo-notifications'}
export function parseProductLink(hash:string){
 const params=new URLSearchParams(hash.replace(/^#/,'')),view=params.get('huohuo-view'),mandate=params.get('mandate')
 if(!view||!Object.hasOwn(views,view)||[...params.keys()].some(k=>!['huohuo-view','mandate'].includes(k))||params.getAll('huohuo-view').length!==1||params.getAll('mandate').length>1)return null
 if(mandate&&(view!=='mandates'||!/^MND_[a-f0-9]{32}$/.test(mandate)))return null
 return {view,mandate}
}
export function installProductNavigation(ctx:DshUiContext){
 ctx.effect(()=>{
  const open=(hash:string)=>{
   const target=parseProductLink(hash);if(!target)return false
   if(target.mandate){sessionStorage.setItem('huohuo-return',JSON.stringify({mandate:target.mandate}));window.dispatchEvent(new CustomEvent('huohuo-mandate-view',{detail:target.mandate}))}
   ctx.layout.selectPanel(views[target.view]);return true
  }
  const click=(event:MouseEvent)=>{
   const a=(event.target as Element)?.closest?.('a[href]');if(!a||event.button!==0||event.metaKey||event.ctrlKey)return
   const url=new URL(a.getAttribute('href')!,window.location.href)
   if(url.origin===window.location.origin&&url.pathname===window.location.pathname&&open(url.hash)){event.preventDefault();event.stopPropagation()}
  }
  const hash=()=>{open(window.location.hash)}
  document.addEventListener('click',click,true);window.addEventListener('hashchange',hash);hash()
  return()=>{document.removeEventListener('click',click,true);window.removeEventListener('hashchange',hash)}
 },'火火受控页面入口')
}
