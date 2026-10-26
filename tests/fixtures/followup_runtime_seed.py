"""隔离 UI 验收数据；明确合成研究，不代表真实 DSH/model/provider 研究。"""
import json,sys
from pathlib import Path
from huohuo.execution import Repository
from huohuo.mandates import Mandates
c=json.loads(Path(sys.argv[1]).read_text());core=Mandates(Repository(Path(c['database'])),'uat');p=c['principal']
core.entities.directory=lambda:{'status':'ok','rows':[{'code':'600519','name':'贵州茅台'}],'source':{'provider':'明确合成目录'}}
r=core.entities.resolve(p,'test','600519');confirmed=core.entities.confirm(p,'test',r['snapshot_id'],r['version'],{r['mentions'][0]['mention_id']:'SEC:CN:A:600519'},'synthetic')
sc={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'financial_summary','period':'20260630','metric':'营业总收入','basis':'source_abstract'}
if len(sys.argv)>2:
    assert sys.argv[2]=='quote', 'unknown fixture case'
    sc={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'}
    m=core.create(p,{'session_id':'test','confirmation_id':confirmed['confirmations'][0]['confirmation_id'],'request_key':'synthetic-quote-delivery','goal':'明确合成验收：单位明确的报价变化，验证应用内投递','scope':sc,'contact_note':'仅应用内合成验收，不外发'})
    core.tick();print(json.dumps({'mandate_id':m['mandate']['mandate_id']}));core.store.close();sys.exit(0)
from huohuo.research_entities.bounded import collect
doc=collect(sc,lambda _: {'code':'600519','records':[{'指标':'营业总收入','20260630':100}]})
m=core.create(p,{'session_id':'test','confirmation_id':confirmed['confirmations'][0]['confirmation_id'],'request_key':'synthetic-ui-seed','goal':'明确合成验收：财务资料变化回访，不代表真实研究','scope':sc,'contact_note':'仅在本实例内查看，不外发'})
core.tick();j=core.repo.claim('synthetic-seed');e=core.repo.save_evidence(j['attempt_id'],j['lease_token'],doc)
core.repo.finish(j['attempt_id'],j['lease_token'],{'status':'succeeded','execution_id':j['execution_id'],'scope':sc,'summary':'明确合成验收结果，不代表真实模型结论','evidence_ids':[e['evidence_id']],'judgements':{'notable_change':{'judgement':'unknown','reason':'明确合成比较结果','evidence_refs':[e['evidence_id']]}}})
core.notifications.tick=lambda:None
core.tick()
core.notifications.save(p,{'expected_revision':0,'enabled':True,'channels':['app'],'timezone':'Asia/Shanghai','quiet_hours':None})
changed=collect(sc,lambda _: {'code':'600519','records':[{'指标':'营业总收入','20260630':101}]})
core.sources.accept(p,changed);core.tick()
print(json.dumps({'mandate_id':m['mandate']['mandate_id'],'baseline':core.get(p,m['mandate']['mandate_id'])['baseline']}));core.store.close()
