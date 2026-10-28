import type { IndexInjection } from '@deepseek-ai/dsh-host-webserver'

/** DSH owns startup and authentication; this only provides its loading presentation. */
export function bootInjections(): IndexInjection[] {
  return [
    {
      kind: 'style',
      text: '#huohuo-boot{position:fixed;inset:0;z-index:2147483647;display:grid;place-items:center;background:#fff;color:#243451;font:600 clamp(21px,2.6vw,30px)/1.5 system-ui,sans-serif;pointer-events:none}[data-dsh-boot]:has([data-dsh-boot-spinner]){background:#fff!important}[data-dsh-boot]:has([data-dsh-boot-spinner])>*{display:none!important}[data-dsh-boot]:has([data-dsh-boot-spinner])::before{content:"火火，你的投研好伙伴";color:#243451;font:600 clamp(21px,2.6vw,30px)/1.5 system-ui,sans-serif}',
    },
    {
      kind: 'html',
      placement: 'body',
      html: '<div id="huohuo-boot" role="status">火火，你的投研好伙伴</div>',
    },
    {
      kind: 'script',
      placement: 'body',
      text: `(()=>{const node=document.getElementById('huohuo-boot');if(!node)return;const finish=()=>{const boot=document.querySelector('[data-dsh-boot]');if(boot)boot.removeAttribute('aria-hidden');observer.disconnect();node.remove()};const check=()=>{const boot=document.querySelector('[data-dsh-boot]');if(boot&&boot.querySelector('[data-dsh-boot-spinner]'))boot.setAttribute('aria-hidden','true');if((boot&&!boot.querySelector('[data-dsh-boot-spinner]'))||document.querySelector('[data-huohuo-intro-message],[data-huohuo-conversation][data-quiet="true"]'))finish()};const observer=new MutationObserver(check);observer.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['data-quiet']});setTimeout(finish,12000);check()})()`,
    },
  ]
}
