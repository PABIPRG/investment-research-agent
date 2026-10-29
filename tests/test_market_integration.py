"""真实业务链，合成公开资料；没有模型和外部通知调用。"""
import copy
from datetime import datetime, timezone
from huohuo.market.contracts import UNITS
import tempfile
import unittest
from pathlib import Path
from huohuo.execution import Repository
from huohuo.mandates import Mandates
from huohuo.contracts import Invalid
from huohuo.research_partner.market_sources import collect_market, content_version
from huohuo.research_partner.market_bridge import MarketBridge

SCOPE = {'entity_id': 'SEC:CN:A:600519', 'exchange': 'SSE', 'operation': 'market_quote'}
class Market:
    price = 90
    def query(self, request):
        row = {'code':'600519','name':'贵州茅台','price':self.price,'time_known':True,'as_of':datetime.now(timezone.utc).isoformat(),'units':dict(UNITS)}
        return {'status':'ok','stale':False,'complete':True,'as_of':row['as_of'],'warnings':[], 'data':{'items':[row]}}

class MarketIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.path = Path(self.tmp.name)/'business.db'
        self.repo=Repository(self.path); self.core=Mandates(self.repo,'fixture')
        self.market=Market(); self.core.market=self.market
        self.core.entities.directory=lambda:{'status':'ok','rows':[{'code':'600519','name':'贵州茅台'}],'source':{'provider':'fixture'}}
        r=self.core.entities.resolve('alice','test','600519行情')
        c=self.core.entities.confirm('alice','test',r['snapshot_id'],r['version'],{r['mentions'][0]['mention_id']:SCOPE['entity_id']},'fixture')
        self.cid=c['confirmations'][0]['confirmation_id']
    def tearDown(self): self.core.store.close(); self.tmp.cleanup()
    def create(self):
        self.core.notifications.save('alice',{'expected_revision':0,'enabled':True,'channels':['app'],'timezone':'Asia/Shanghai','quiet_hours':None})
        return self.core.create('alice',{'request_key':'create-market','scope':SCOPE,'goal':'合成：价格超过100时提醒','contact_note':'仅应用内', 'session_id':'test','confirmation_id':self.cid,
            'contact_rule':{'mode':'condition','condition':{'type':'numeric','metric':'price','operator':'>','threshold':100},'cooldown_minutes':0}})
    def finish(self, fake_price):
        job=self.repo.claim('fixture'); self.assertIsNotNone(job)
        doc=self.core.bound_source(job['execution_id']) or collect_market(SCOPE,self.market)
        evidence=self.repo.save_evidence(job['attempt_id'],job['lease_token'],doc)
        self.repo.finish(job['attempt_id'],job['lease_token'],{'status':'succeeded','execution_id':job['execution_id'],'scope':SCOPE,'summary':'合成研究；条件由程序判断','evidence_ids':[evidence['evidence_id']],
            'metrics':{'price':{'value':fake_price,'unit':'CNY/share','method_version':'market_v1','evidence_refs':[evidence['evidence_id']]}}})
        self.core.tick()
    def test_numeric_notification_uses_source_not_model_and_persists(self):
        m=self.create(); self.core.tick(); self.finish(9999)
        view=self.core.get('alice',m['mandate']['mandate_id'])
        self.assertEqual(view['decisions'][-1]['condition_result'],'unmet')
        self.assertEqual(view['notifications'],[])
        self.market.price=110
        doc=collect_market(SCOPE,self.market); eid=self.core.sources.accept('alice',doc)
        self.assertEqual(eid,self.core.sources.accept('alice',doc))
        self.core.tick(); self.finish(0)
        view=self.core.get('alice',m['mandate']['mandate_id'])
        self.assertEqual({d['condition_result'] for d in view['decisions']},{'met','unmet'})
        self.assertEqual(len(view['notifications']),1)
        self.assertEqual(view['notifications'][0]['status'],'delivered')
        self.core.store.close(); self.repo=Repository(self.path); self.core=Mandates(self.repo,'fixture')
        self.assertEqual(len(self.core.get('alice',m['mandate']['mandate_id'])['notifications']),1)
    def test_scheduled_delivery_waits_for_due_not_baseline_or_source(self):
        m=self.create(); mid=m['mandate']['mandate_id']
        self.core.command('alice',mid,'revise',{'request_key':'scheduled-rule','expected_revision':1,'expected_generation':0,
            'goal':m['revision']['goal'],'scope':SCOPE,'contact_note':'每日交付',
            'contact_rule':{'mode':'scheduled_delivery','time':'23:59','trading_days_only':False}})
        self.core.tick(); self.assertIsNone(self.repo.claim('before-due'))
        self.assertEqual(self.core.get('alice',mid)['notifications'],[])
        self.market.price=120; self.core.sources.accept('alice',collect_market(SCOPE,self.market)); self.core.tick()
        self.assertIsNone(self.repo.claim('fixture'))
        self.assertEqual(self.core.get('alice',mid)['notifications'],[])
    def test_queued_old_quote_is_history_not_current_notification(self):
        m=self.create(); self.core.tick(); self.finish(0)
        self.market.price=120; doc=collect_market(SCOPE,self.market)
        self.core.sources.accept('alice',doc); self.core.tick()
        clock=self.repo.clock; self.repo.clock=lambda:clock()+240
        self.finish(999)
        view=self.core.get('alice',m['mandate']['mandate_id'])
        self.assertEqual(view['notifications'],[])
        self.assertTrue(view['results'][0]['stale'])
    def test_stale_and_unknown_time_do_not_become_new_source(self):
        response=self.market.query({}); response['stale']=True
        class Source:
            def query(self,_): return response
        doc=collect_market(SCOPE,Source()); self.assertEqual(doc['status'],'unavailable')
        with self.assertRaises(Invalid): self.core.sources.accept('alice',doc)
    def test_empty_news_is_valid_baseline_and_poll_time_not_change(self):
        class News:
            def query(self,_):return {'status':'empty','stale':False,'complete':True,'data':{'items':[]},'warnings':[]}
        scope=dict(SCOPE,operation='news'); doc=collect_market(scope,News()); self.assertEqual(doc['status'],'ok')
        self.assertEqual(self.core.sources.accept('alice',doc),self.core.sources.accept('alice',doc))
        later=copy.deepcopy(doc); later['values']['observed_at']='later'
        self.assertEqual(content_version(doc),content_version(later))
    def test_query_requires_confirmation_and_reuses_receipt(self):
        bridge=MarketBridge(self.repo,self.core.entities,self.market)
        with self.assertRaises(Invalid):bridge.run('alice','other','call',{'operation':'quotes','confirmation_id':self.cid})
        value=bridge.run('alice','test','call',{'operation':'quotes','confirmation_id':self.cid})
        self.market.price=120
        self.assertEqual(value,bridge.run('alice','test','call',{'operation':'quotes','confirmation_id':self.cid}))
        self.assertFalse(value['monitoring_created'])
        self.assertEqual([],self.core.list('alice')['items'])
    def test_extended_news_reaches_existing_provider_without_new_monitor(self):
        from huohuo.market.contracts import validate
        calls=[]
        class Source:
            def query(self, request):
                calls.append(validate(request))
                return {'status':'empty','stale':False,'complete':True,'data':{'items':[]}}
        bridge=MarketBridge(self.repo,self.core.entities,Source())
        value=bridge.run('alice','test','extended',{'operation':'news','include_slow':True})
        self.assertTrue(calls[0]['include_slow'])
        self.assertFalse(value['monitoring_created'])
        with self.assertRaises(Invalid):
            bridge.run('alice','test','directed',{'operation':'news','include_slow':True,'confirmation_id':self.cid})
        self.assertEqual([],self.core.list('alice')['items'])
