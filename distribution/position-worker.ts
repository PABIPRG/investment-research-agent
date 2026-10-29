import {setTimeout as delay} from 'node:timers/promises'
import {request,type Instance} from './instance.js'
import type {RuntimeObserver} from './observation.js'

export async function runPositionAttempt(config:Instance,job:any,signal:AbortSignal,observer?:RuntimeObserver,
  route?:{path:'program-run';observation:string}):Promise<'completed'|'uncertain'>{
  const stopped=new AbortController(),path=`/worker/attempts/${job.attempt_id}`
  const heartbeat=(async()=>{while(!stopped.signal.aborted&&!signal.aborted){
    try{await delay(5000,undefined,{signal:stopped.signal});await request(config,path+'/heartbeat',{},'worker',job.lease_token)}
    catch{stopped.abort();return}
  }})()
  try{
    if(signal.aborted)return 'uncertain'
    try{observer?.({kind:route?.observation??(job.price_rule?'program.price-rule':'program.position-rule'),observed_at:new Date().toISOString(),execution_id:job.execution_id,attempt_id:job.attempt_id})}catch{/* 观察失败不影响价格规则。 */}
    await request(config,path+'/'+(route?.path??(job.price_rule?'price-run':'position-run')),{},'worker',job.lease_token,AbortSignal.any([signal,stopped.signal]))
    return 'completed'
  }catch{return 'uncertain'}finally{stopped.abort();await heartbeat}
}
