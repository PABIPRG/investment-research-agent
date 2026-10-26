"""隔离 UI 验收数据；明确合成研究，不代表真实 DSH/model/provider 研究。"""
import json,sys
from pathlib import Path
from huohuo.execution import Repository
from huohuo.mandates import Mandates
c=json.loads(Path(sys.argv[1]).read_text());core=Mandates(Repository(Path(c['database'])),'uat');p=c['principal']
core.entities.directory=lambda:{'status':'ok','rows':[{'code':'600519','name':'贵州茅台'}],'source':{'provider':'明确合成目录'}}
r=core.entities.resolve(p,'test','600519');confirmed=core.entities.confirm(p,'test',r['snapshot_id'],r['version'],{r['mentions'][0]['mention_id']:'SEC:CN:A:600519'},'synthetic')
sc={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'}
m=core.create(p,{'session_id':'test','confirmation_id':confirmed['confirmations'][0]['confirmation_id'],'request_key':'synthetic-ui-seed','goal':'明确合成验收：财务资料变化回访，不代表真实研究','scope':sc,'contact_note':'仅在本实例内查看，不外发'})
core.tick();j=core.repo.claim('synthetic-seed');e=core.repo.save_evidence(j['attempt_id'],j['lease_token'],{'status':'ok','scope':sc,'source':'明确合成验收来源','source_url':'https://example.invalid/followup-uat','observed_at':'2026-10-23T08:00:00Z','values':{'price':'10'}})
core.repo.finish(j['attempt_id'],j['lease_token'],{'status':'succeeded','execution_id':j['execution_id'],'scope':sc,'summary':'明确合成验收结果，不代表真实模型结论','evidence_ids':[e['evidence_id']],'judgements':{'notable_change':{'judgement':'met','reason':'明确合成比较结果','evidence_refs':[e['evidence_id']]}}})
core.notifications.tick=lambda:None
core.tick();print(json.dumps({'mandate_id':m['mandate']['mandate_id']}));core.store.close()
