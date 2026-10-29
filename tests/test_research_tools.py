import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates
from huohuo.contracts import Invalid
from huohuo.research_entities.confirmation import EntityConfirmation
from huohuo.research_entities.tool_bridge import ResearchToolBridge
from huohuo.research_entities.tool_contracts import catalog, validate_args
from huohuo.research_entities.registry.tools import TOOL_REGISTRY
from huohuo.research_entities.toolbox.registry import HANDLERS, validate_toolbox
from huohuo.research_entities.toolbox.contracts import ToolResult
from huohuo.research_entities.toolbox.context import ToolUnavailable

class ResearchToolTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=1000
  self.repo=Repository(Path(self.tmp.name)/'db.sqlite',clock=lambda:self.now)
  self.core=Mandates(self.repo,'test')
  self.entities=EntityConfirmation(self.repo,directory=lambda:{'status':'ok','rows':[{'code':'600519','name':'贵州茅台'}],'source':{'provider':'fixture'}})
  self.bridge=ResearchToolBridge(self.repo,self.entities)
 def tearDown(self):
  self.core.store.close();self.tmp.cleanup()
 def confirm(self, eid='SEC:CN:A:600519'):
  snap=self.entities.resolve('alice','chat','贵州茅台')
  return self.entities.confirm('alice','chat',snap['snapshot_id'],snap['version'],{snap['mentions'][0]['mention_id']:eid},'native')['confirmations'][0]['confirmation_id']
 def test_catalog_complete_and_registry_semantics(self):
  entries=catalog();self.assertEqual(len(entries),67);self.assertEqual({x['name'] for x in entries},set(HANDLERS));self.assertEqual(validate_toolbox(),[])
  for entry in entries:
   self.assertEqual(entry['availability'],TOOL_REGISTRY[entry['name']].availability)
   self.assertNotIn('authorized',entry['parameters']['properties'])
   self.assertNotIn('session_id',entry['parameters']['properties'])
 def test_validation_rejects_identity_override_and_bad_types(self):
  for args in [{'confirmation_id':'x','code':'000001'},{'confirmation_id':'x','limit':True},{'confirmation_id':'x','days':0},{'confirmation_id':'x','start_date':'2026-02-30'},{'confirmation_id':'x','authorized':True}]:
   with self.assertRaises(Invalid):validate_args('quote_history',args)
 def test_live_local_handler_and_durable_result(self):
  snap=self.entities.resolve('alice','chat','人形机器人');m=snap['mentions'][0]
  cid=self.entities.confirm('alice','chat',snap['snapshot_id'],snap['version'],{m['mention_id']:m['candidates'][0]['entity_id']},'native')['confirmations'][0]['confirmation_id']
  r=self.bridge.run('alice','chat','c1','theme_lookup',{'confirmation_id':cid})
  self.assertEqual(r['status'],'ok');self.assertIn('人形机器人',str(r['data']))
  self.assertEqual(ResearchToolBridge(self.repo,self.entities).evidence('alice','chat',r['evidence_id']),r)
  with self.assertRaises(Invalid):self.bridge.evidence('alice','other',r['evidence_id'])
 def test_confirmed_binding_replay_and_expiry(self):
  cid=self.confirm();seen=[]
  def handler(call):
   seen.append(call.entities[0].entity_id)
   return ToolResult(tool_id=call.tool_id,status='ok',data={'records':[{'value':1}]},source='fixture')
  with patch.dict(HANDLERS,{'quote_history':handler}):
   result=self.bridge.run('alice','chat','c1','quote_history',{'confirmation_id':cid})
   self.assertEqual(self.bridge.run('alice','chat','c1','quote_history',{'confirmation_id':cid}),result)
   self.assertEqual(seen,['SEC:CN:A:600519'])
   with self.assertRaises(Conflict):self.bridge.run('alice','chat','c1','quote_history',{'confirmation_id':cid,'limit':1})
   for user,session in [('bob','chat'),('alice','other')]:
    with self.assertRaises(Invalid):self.bridge.run(user,session,'c2','quote_history',{'confirmation_id':cid})
   self.now+=3601
   with self.assertRaises(Invalid):self.bridge.run('alice','chat','c2','quote_history',{'confirmation_id':cid})
 def test_monitor_does_not_run_without_program_authorization(self):
  def forbidden(_):raise AssertionError('must not execute')
  with patch.dict(HANDLERS,{'event_monitor_setup':forbidden}):
   self.assertEqual(self.bridge.run('alice','chat','c','event_monitor_setup',{})['status'],'needs_authorization')
 def test_failure_is_evidence_not_empty_data(self):
  cid=self.confirm()
  def failure(_):raise ToolUnavailable('fixture source unavailable')
  with patch.dict(HANDLERS,{'quote_history':failure}):
   r=self.bridge.run('alice','chat','c','quote_history',{'confirmation_id':cid})
  self.assertEqual(r['status'],'unavailable');self.assertEqual(self.bridge.evidence('alice','chat',r['evidence_id']),r)
 def test_company_cannot_be_used_as_stock(self):
  cid=self.confirm('CO:CN:A:600519')
  with self.assertRaises(Invalid):self.bridge.run('alice','chat','c','quote_history',{'confirmation_id':cid})
 def test_legacy_service_is_not_probed(self):
  self.assertEqual(self.bridge.run('alice','chat','c','strategy_pool_lookup',{})['status'],'unavailable')

 def test_security_discovery_reuses_public_directory_without_confirmation(self):
  with patch('huohuo.research_entities.tool_bridge.search_securities',return_value={'status':'ok','candidates':[{'code':'600519','name':'贵州茅台'}],'source':{'provider':'fixture'}}):
   result=self.bridge.run('alice','chat','discover','security_lookup',{'code':'600519'})
  self.assertEqual(result['status'],'ok')
  self.assertEqual(self.entities.current('alice','chat'),[])
  with patch('huohuo.research_entities.tool_bridge.search_securities',return_value={'status':'unavailable','source':{'provider':'fixture'}}):
   self.assertEqual(self.bridge.run('alice','chat','failure','security_lookup',{'code':'600519'})['status'],'unavailable')
