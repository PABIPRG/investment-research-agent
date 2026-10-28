import json
import tempfile
from pathlib import Path
from huohuo.contracts import canonical
from huohuo.execution import Repository,digest
from huohuo.mandates import Mandates
from huohuo.transfer import TransferService


def snapshot(version=4):
    collections={
        'holdings':{'holdings':{'default':[{'ticker':'600519','quantity':10,'cost_price':100,'position_time':'2025-01-01T09:30:00+08:00'}]},
                    'trades':{'entries':[{'ticker':'600519','name':'贵州茅台','side':'buy','price':100,'quantity':10,'amount':1000,'traded_at':'2025-01-01T09:30','trade_id':'one','source':'broker','account_mode':'real','occurred':1}]}},
        'watchlist':{'watchlist':{'default':['000001']}},
        'strategies':{'strategies':{'old-strategy':{'name':'双均线观察','kind':'ma_cross','params':{'fast':5,'slow':20},'symbols':['600519'],'direction':'利好','status':'active','backtest':{'return':500}}},'strategy_backtests':{'old-run':{'status':'completed','return':500}}},
        'research':{'reports':{'report-1':{'title':'旧合成报告','content':'保留的历史内容','api_key':'synthetic-only-not-a-credential'}},'research_chat_contexts':{'chat-1':{'title':'旧讨论','messages':['合成回放']}}},
        'preferences':{'preferences':{'secret':{'api_key':'synthetic-only-not-a-credential'}}},
    }
    if version==1: collections['holdings'].pop('trades')
    return {'backend':'trading-core','schemaVersion':version,'categories':{key:{'collections':value,'count':len(value)} for key,value in collections.items()},'revision':digest(collections)}


def package(snapshot_value=None,mandates=None):
    payload=snapshot_value or snapshot();domains={}
    domains['trading-core']={'schemaVersion':str(payload['schemaVersion']),'consistencyVersion':payload['revision'],'counts':{},'checksum':{'algorithm':'sha256','value':digest(payload)},'payload':payload}
    if mandates is not None:
        mp={'format':'research-partner-data-package','format_version':1,'domain':'research-partner','schema_version':'1.0','mandates':mandates,'integrity':{'algorithm':'sha256','value':digest(mandates)}}
        domains['research-partner']={'schemaVersion':'1.0','checksum':{'algorithm':'sha256','value':digest(mp)},'payload':mp}
    body={'format':'pa-product-data-package','formatVersion':1,'createdAt':'2025-01-02T00:00:00Z','exportScope':{'domains':list(domains),'attachments':[]},'domains':domains,'missing':[],'complete':True,'attachments':[]}
    return {**body,'integrity':{'algorithm':'sha256','value':digest(body)}}


def mandate_entry():
    mid='MND_'+'1'*32;at='2025-01-02T00:00:00+00:00'
    return {'mandate':{'mandate_id':mid,'principal_id':'old-owner','instance_id':'old-instance','status':'tracking','current_revision':1,'source_session_id':'old-chat','created_at':at,'updated_at':at},
        'revisions':[{'revision':{'mandate_id':mid,'revision':1,'goal':'旧委托关注财报','scope':{'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'},'triggers':[],'contact_policy':{'channels':['wecom'],'authorized':True},'basis':{},'created_by':'old-owner','created_at':at},'subjects':[],'requirements':[],'dependencies':[]}],
        'schedules':[{'schedule_id':'SCH_'+'2'*32,'mandate_id':mid,'revision':1,'mode':'due_reminder','cron':'0 12 * * *','timezone':'Asia/Shanghai','next_due_at':at,'enabled':True,'created_at':at,'updated_at':at}]}


class Fixture:
    def __init__(self,directory):
        self.repo=Repository(Path(directory)/'db.sqlite')
        self.core=Mandates(self.repo,'new-instance')
        self.store=self.core.store
        self.clock=1800000000
        self.service=TransferService(self.store,'new-instance',clock=lambda:self.clock,name_resolver=lambda code:{'600519':'贵州茅台','000001':'平安银行'}.get(code,''))
        self.n=0
    def upload(self,value=None):
        self.n+=1
        return self.service.upload('owner','chat',{'request_key':f'upload-{self.n}','filename':'旧数据.json','content':json.dumps(value or snapshot(),ensure_ascii=False)})
    def preview(self,upload,selected=None,rules=None):
        self.n+=1
        return self.service.prepare('owner','chat',{'request_key':f'preview-{self.n}','upload_id':upload['upload_id'],'selected':selected or [x['id'] for x in upload['categories']],'rules':rules or {}})
    def commit(self,preview,owner='owner',session='chat'):
        return self.service.commit(owner,session,{key:preview[key] for key in ('preview_id','request_key')})
