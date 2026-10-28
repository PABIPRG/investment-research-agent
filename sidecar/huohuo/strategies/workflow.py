"""明确确认后的单次流程；网络在事务外，写入在资格复核后一次提交。"""
import json
from datetime import datetime,timezone
from ..contracts import canonical,Invalid
from ..execution import Conflict
from .legacy import evolution,shadow,genome,regime,ledger
from .legacy.runtime import runtime,settings
from .calculations import backtest,shadow_result,MODEL_NOTE
from . import market

def execute(service,docs,preview,run,payload,authorize=None,finalize=None):
    preview=dict(preview)
    db=service.store._connect();sid=payload.get('strategy_id') or payload.get('id')
    action=preview['action'];evidence=[];updates=[];result={}
    try:
        with runtime(service.clock):
            if authorize:authorize()
            strategy=docs.get('strategies',sid)
            if action=='events':
                from .event_sources import collect
                events=collect(service,payload['securities'])
            elif action=='backtest':
                report,evidence=backtest(strategy,payload,service.history,service.clock)
                result={'backtest':report}
            elif action=='shadow':
                day,snapshot,updates,evidence=shadow_result(strategy,docs,service.history,service.today(),service.clock)
                result={'day':day,'snapshot':snapshot}
                values,ev=market.load(service,day)
                result.update(values);evidence+=ev
            elif action=='recall':
                day=service.today().isoformat()
                values,ev=market.load(service,day)
                result.update(values);evidence+=ev
            # One transaction covers evidence, strategy, every action, child, archive and receipt.
            with service.store.transaction():
                current=db.execute('SELECT * FROM strategy_runs WHERE id=?',(run,)).fetchone()
                if current['status']!='running':raise Conflict('运行已取消或中断，未写入迟到结果')
                if authorize:authorize()
                if docs.version()!=preview['state_version']:raise Conflict('计算期间策略或证据已变化，本次结果未生效；请刷新核对')
                stamp=datetime.fromtimestamp(service.clock(),timezone.utc).isoformat()
                if action=='events':
                    from .planner import ingest
                    result.update(ingest(service,docs.principal,events))
                    result['event_count']=len(events)
                    result['note']='新闻已读取，候选由 DSH 单独研究；正式保存仍需确认' if events else '本次来源读取成功，没有新事件'
                elif action=='recall':
                    from . import schedule,suggestions
                    market.save(docs,day,result)
                    result.update(suggestions.recall(service,docs,schedule.read(service,docs.principal)))
                elif action=='schedule':
                    from .schedule import apply
                    result['automation']=apply(service,docs,payload)
                elif action=='accept_suggestion':
                    from .suggestions import accept
                    strategy=accept(service,docs,payload,stamp)
                    db.execute('INSERT OR IGNORE INTO strategy_run_subjects VALUES(?,?,?)',(run,docs.principal,strategy['id']))
                elif action=='create':
                    strategy={**payload,'revision':1,'status':'candidate','verification_status':'insufficient',
                        'backtest':{},'source':'user_confirmed_hypothesis','created_at':stamp,'updated_at':stamp,
                        'evolve':{'state':'active','tier':1}}
                    source_type='research:'+payload['source_refs'][0]['tool'] if payload['source_refs'] else 'user_hypothesis'
                    strategy['gene']=genome.gene_for(strategy['kind'],strategy['params'],strategy['symbols'],strategy['direction'],event_type=source_type)
                    strategy['source_kind']=source_type
                    ledger.record_candidate(docs,event={'event_type':source_type,'date':stamp[:10]},direction=strategy['direction'],symbol_codes=strategy['symbols'],date=stamp[:10])
                    docs.set('strategies',sid,strategy)
                elif action=='backtest':
                    strategy={**strategy,'status':'active' if strategy['status']=='candidate' else strategy['status'],
                        'verification_status':report['verification_status'],'backtest':{**report,'ran_at':stamp},
                        'revision':strategy['revision']+1,'updated_at':stamp}
                    docs.set('strategies',sid,strategy)
                elif action=='shadow':
                    market.save(docs,day,result)
                    existing=(docs.get('shadow_equity',day) or {}).get('strategies',{}).get(sid)
                    kept,hibernated=shadow._regime_hibernation([strategy],docs,day)
                    if authorize and existing:
                        result.pop('snapshot',None)
                        result['skipped']='该交易日已有影子验证记录，未重复写入'
                    elif hibernated:
                        result.pop('snapshot',None)
                        result['skipped']='当前市场环境不在策略适配范围；本次冬眠，未写净值或模拟成交'
                    else:
                        for collection,key,value in updates:docs.set(collection,key,value)
                        old=docs.get('shadow_equity',day) or {'date':day,'strategies':{}}
                        old['strategies'][sid]=snapshot
                        old['overall_nav']=shadow._overall_nav(old['strategies'])
                        docs.set('shadow_equity',day,old)
                elif action=='retire':
                    strategy={**strategy,'status':'retired','revision':strategy['revision']+1,'updated_at':stamp}
                    docs.set('strategies',sid,strategy)
                    from .legacy import gene_archive
                    gene_archive.archive_record(docs,strategy,reason='user_confirmed_retirement')
                elif action in ('evolve','apply'):
                    before=docs.all('strategies')
                    result['evolution']=evolution.evolve(docs,apply=action=='apply',preview_token=payload.get('preview_token'),strategy_id=sid)
                    if action=='apply':
                        for key,value in docs.all('strategies').items():
                            if before.get(key)!=value:
                                value['revision']=before.get(key,{}).get('revision',0)+1
                                value['updated_at']=stamp
                                if not value.get('securities'):
                                    names={s['code']:s['name'] for rec in before.values() for s in rec.get('securities',[])}
                                    value['securities']=[{'code':code,'name':names.get(code,'证券名称待补充')} for code in value['symbols']]
                                parent=before.get(value.get('mutated_from'),{})
                                if parent:
                                    value['source_refs']=parent.get('source_refs',[])
                                    value['source_evidence_ids']=parent.get('source_evidence_ids',[])
                                    value['gene']['scope']=parent.get('gene',{}).get('scope',value['gene'].get('scope',{}))
                                docs.set('strategies',key,value)
                                db.execute('INSERT OR IGNORE INTO strategy_run_subjects VALUES(?,?,?)',(run,docs.principal,key))
                        strategy=docs.get('strategies',sid)
                for i,ev in enumerate(evidence):
                    db.execute('INSERT INTO strategy_run_evidence VALUES(?,?,?,?)',(run+':'+str(i),docs.principal,run,canonical(ev)))
                if len(docs.all('strategies'))>100:raise Conflict('本次动作将超过 100 项策略上限，整批未应用')
                summaries=[{k:v for k,v in ev.items() if k!='records'} for ev in evidence]
                result.update(evidence=summaries,model_note=MODEL_NOTE)
                db.execute("UPDATE strategy_runs SET status=?,result=?,updated_at=? WHERE id=?",('skipped' if result.get('skipped') else 'completed',canonical(result),service.clock(),run))
                receipt={'strategy':strategy,'run':service.run_view(db.execute('SELECT * FROM strategy_runs WHERE id=?',(run,)).fetchone()),**result}
                if preview.get('id'):db.execute("UPDATE strategy_previews SET status='committed',result=? WHERE id=?",(canonical(receipt),preview['id']))
                if finalize: finalize(receipt)
                return receipt
    except Exception as exc:
        # Rollback the entire domain transaction first; preserve a separate failed receipt.
        from ..research_entities.toolbox.context import ToolUnavailable
        detail=str(exc) if isinstance(exc,(Conflict,ToolUnavailable,Invalid)) else '策略计算失败，未将本次结果写入正式策略；请核对输入与资料来源'
        with service.store.transaction():
            r=db.execute('SELECT * FROM strategy_runs WHERE id=?',(run,)).fetchone()
            if r['status']=='running':db.execute("UPDATE strategy_runs SET status='failed',error=?,updated_at=? WHERE id=?",(detail,service.clock(),run))
            receipt={'strategy':docs.get('strategies',sid),'run':service.run_view(db.execute('SELECT * FROM strategy_runs WHERE id=?',(run,)).fetchone())}
            if preview.get('id'):db.execute("UPDATE strategy_previews SET status='failed',result=? WHERE id=?",(canonical(receipt),preview['id']))
            if finalize and receipt['run']['status']=='failed':
                try: finalize(receipt)
                except Conflict: pass
            return receipt
