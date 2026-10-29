"""通过真实 loopback HTTP 验证新增装配，不向公网请求。"""
import threading
import tempfile
import unittest
import urllib.request
import urllib.error
import json
from pathlib import Path
from huohuo.server import Service
from test_industry_chain_fixtures import Source as FakeSource

class RuntimeCapabilitiesApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.service=Service({'host':'127.0.0.1','port':0,'principal':'alice','user_token':'user','worker_token':'worker','database':str(Path(self.tmp.name)/'state.db')})
        self.thread=threading.Thread(target=self.service.serve_forever,daemon=True);self.thread.start()
        self.source=FakeSource();self.service.industry_chain.seed.http_get=self.source
    def tearDown(self):
        self.service.shutdown();self.thread.join();self.service.server_close();self.service.mandates.store.close();self.tmp.cleanup()
    def call(self,path,body=None,token='user'):
        request=urllib.request.Request(f'http://127.0.0.1:{self.service.server_port}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as r:return r.code,json.load(r)
    def test_data_lifecycle_reachable_and_confirmed(self):
        self.assertEqual(self.call('/industry-chain')[1]['state'],'missing')
        status,p=self.call('/industry-chain/prepare',{'session_id':'ui','request_key':'download','action':'bootstrap','payload':{'acknowledge_source_terms':True}})
        self.assertEqual(status,200);self.assertEqual(self.source.calls,[])
        self.assertEqual(self.call('/industry-chain/commit',{'session_id':'wrong','preview_id':p['preview_id'],'request_key':'download'})[0],404)
        status,r=self.call('/industry-chain/commit',{'session_id':'ui','preview_id':p['preview_id'],'request_key':'download'})
        self.assertEqual(status,200);self.assertEqual(r['status'],'committed')
        status,r=self.call('/industry-chain/query',{'path':'/companies','params':{'keyword':'核心'}})
        self.assertEqual(r['data']['items'][0]['name'],'核心甲')
    def test_worker_strategy_endpoints_require_worker_and_no_plan_no_work(self):
        self.assertEqual(self.call('/worker/strategies/tick',{})[0],403)
        status,value=self.call('/worker/strategies/tick',{},'worker');self.assertEqual(status,200)
        self.assertEqual(self.call('/worker/strategies/planner/claim',{'worker_id':'worker'},'worker'),(200,None))
    def test_market_route_and_role_validation(self):
        body={'session_id':'test','call_id':'test','arguments':{'operation':'scan','kind':'gainers'}}
        self.assertEqual(self.call('/market/query',body,'worker')[0],403)
        self.service.market.query=lambda args:{'status':'ok','data':{'items':[]},'request':args}
        status,result=self.call('/market/query',body)
        self.assertEqual(status,200);self.assertEqual(result['request']['kind'],'gainers')
        self.assertFalse(result['monitoring_created'])

    def test_calendar_outage_does_not_block_discovery_and_claim(self):
        self.service.calendar.refresh=lambda: (_ for _ in ()).throw(RuntimeError('calendar down'))
        self.assertEqual(self.call('/worker/discover',{},'worker'),(200,{'checked':False,'calendar':'unavailable'}))
        self.assertEqual(self.call('/worker/claim',{'worker_id':'fixture'},'worker'),(200,None))

    def test_research_tool_reuses_instance_chain_and_keeps_session_evidence(self):
        core=self.service.mandates
        core.entities.directory=lambda:{'status':'ok','rows':[{'code':'600001','name':'核心甲'}], 'source':{'provider':'synthetic'}}
        resolved=core.entities.resolve('alice','chat','600001股票')
        confirmation=core.entities.confirm('alice','chat',resolved['snapshot_id'],resolved['version'],
            {resolved['mentions'][0]['mention_id']:'SEC:CN:A:600001'},'selected')['confirmations'][0]['confirmation_id']
        body={'session_id':'chat','call_id':'before','tool_id':'industry_chain_lookup','arguments':{'confirmation_id':confirmation}}
        self.assertEqual(self.call('/research-tools/run',body)[1]['status'],'unavailable')
        _,preview=self.call('/industry-chain/prepare',{'session_id':'ui','request_key':'seed','action':'bootstrap','payload':{'acknowledge_source_terms':True}})
        self.call('/industry-chain/commit',{'session_id':'ui','preview_id':preview['preview_id'],'request_key':'seed'})
        body['call_id']='after'
        status,result=self.call('/research-tools/run',body)
        self.assertEqual(status,200);self.assertEqual(result['status'],'ok')
        self.assertIn('核心甲',json.dumps(result,ensure_ascii=False))
        self.assertEqual(self.service.research_tools.evidence('alice','chat',result['evidence_id']),result)
        body['session_id']='other';body['call_id']='cross-session'
        self.assertEqual(self.call('/research-tools/run',body)[0],400)

    def test_transfer_upload_preview_commit_and_identity(self):
        from test_transfer_fixtures import package,mandate_entry
        body={'session_id':'ui-transfer-owner','request_key':'fixture-upload','filename':'synthetic.json','content':json.dumps(package(mandates=[mandate_entry()]))}
        self.assertEqual(self.call('/transfer/upload',body,'worker')[0],403)
        status,upload=self.call('/transfer/upload',body);self.assertEqual(status,200)
        self.assertEqual(self.service.investment.read('alice')['version'],0)
        status,preview=self.call('/transfer/prepare',{'session_id':'ui-transfer-owner','request_key':'fixture-preview','upload_id':upload['upload_id'],'selected':['holdings','watchlist','strategies','research','mandates'],'rules':{}})
        self.assertEqual(status,200);self.assertTrue(preview['can_commit'])
        command={'session_id':'wrong','request_key':preview['request_key'],'preview_id':preview['preview_id']}
        self.assertEqual(self.call('/transfer/commit',command)[0],404)
        command['session_id']='ui-transfer-owner'
        status,receipt=self.call('/transfer/commit',command);self.assertEqual(status,200)
        self.assertEqual(receipt['status'],'committed')
        self.assertEqual(self.call('/transfer/commit',command)[1],receipt)
        facts=self.service.investment.read('alice')
        self.assertEqual(facts['version'],1);self.assertEqual(facts['holdings'][0]['quantity'],10)
        self.assertFalse(facts['trades'][0]['affects_holdings'])
        self.assertEqual(self.call('/transfer/archive',{'session_id':'ui-transfer-owner'})[1]['total'],receipt['result']['archives_added'])
        self.assertEqual(self.call('/transfer/status',{'session_id':'ui-transfer-owner','preview_id':preview['preview_id']})[1]['receipt'],receipt)

    def test_transfer_rejects_paths_and_extra_identity(self):
        from test_transfer_fixtures import snapshot
        body={'session_id':'ui','request_key':'bad','filename':'/private/data.json','content':json.dumps(snapshot())}
        self.assertEqual(self.call('/transfer/upload',body)[0],400)
        self.assertEqual(self.call('/transfer/uploads',{'session_id':'ui','principal':'someone'})[0],400)
        self.assertEqual(self.call('/transfer/uploads')[0],400)
