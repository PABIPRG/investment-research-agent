"""真实 loopback HTTP 与侧车工具桥；不访问任何外部数据源。"""
import json,tempfile,threading,unittest
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from huohuo.server import Service

class StrategyApi(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.server=Service({'host':'127.0.0.1','port':0,'database':str(Path(self.tmp.name)/'api.sqlite'),
      'principal':'alice','instance_id':'strategy-api-tests','user_token':'test-user','worker_token':'test-worker'})
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.client=build_opener(ProxyHandler({}))
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join();self.server.mandates.store.close();self.tmp.cleanup()
 def call(self,path,body=None,token='test-user',attempt=None):
  req=Request(f'http://127.0.0.1:{self.server.server_port}'+path,
      data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json',**({'X-Attempt-Token':attempt} if attempt else {})})
  try:
   with self.client.open(req,timeout=3) as r:return r.status,json.load(r)
  except HTTPError as e:
   with e:return e.code,json.load(e)
 def test_duplicate_port_cannot_interrupt_existing_strategy_runs(self):
  from unittest.mock import patch
  from huohuo.strategies.service import Strategies
  config={**self.server.config,'port':self.server.server_port}
  with patch.object(Strategies,'recovery') as recover:
   with self.assertRaises(OSError):Service(config)
   recover.assert_not_called()
 def test_auth_and_no_browser_identity_override(self):
  self.assertEqual(self.call('/strategies',token='wrong')[0],403)
  self.assertEqual(self.call('/strategies/query',{'principal':'bob'})[0],400)
  status,data=self.call('/strategies');self.assertEqual(status,200)
  self.assertEqual(data['strategies'],[]);self.assertIsNone(data['attribution']['overall'])
 def test_three_real_research_tools_share_local_owner_state(self):
  create={'session_id':'chat','request_key':'create-one','action':'create','payload':{
      'name':'接口测试候选','kind':'momentum','params':{'n':10},'direction':'利好',
      'securities':[{'code':'600519','name':'贵州茅台'}],'rationale':'明确合成接口测试'}}
  _,p=self.call('/strategies/prepare',create)
  self.assertEqual(self.call('/strategies')[1]['strategies'],[])
  code,result=self.call('/strategies/commit',{'session_id':'chat','preview_id':p['preview_id'],'request_key':'create-one'})
  self.assertEqual(code,200);self.assertEqual(result['run']['status'],'completed')
  for name in ['strategy_pool_lookup','strategy_attribution_lookup','strategy_evolution_preview']:
   code,value=self.call('/research-tools/run',{'session_id':'chat','call_id':name,'tool_id':name,'arguments':{}})
   self.assertEqual(code,200);self.assertIn(value['status'],('ok','empty'))
   self.assertEqual(value['source'],'huohuo-sidecar:strategy')
   self.assertTrue(value['evidence_id'])
  self.assertEqual(self.call('/strategies')[1]['pool']['counts']['candidate'],1)
  self.assertEqual(self.call('/strategies/query',{'request_key':'create-one'})[1]['runs'][0]['request_key'],'create-one')
