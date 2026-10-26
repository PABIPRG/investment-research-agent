import tempfile
import unittest
from pathlib import Path
from huohuo.execution import Repository
from huohuo.mandates import Mandates
from huohuo.contracts import Invalid
from huohuo.research_entities.confirmation import EntityConfirmation

ROWS=[{'code':'600519','name':'贵州茅台','aliases':['茅台']},{'code':'000001','name':'平安银行','aliases':['平安']},{'code':'601318','name':'中国平安','aliases':['平安']}]
class EntityConfirmationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=1000
  self.repo=Repository(Path(self.tmp.name)/'test.sqlite',clock=lambda:self.now)
  self.core=Mandates(self.repo,'test');self.entities=EntityConfirmation(self.repo, directory=lambda:{'status':'ok','rows':ROWS,'source':{'provider':'fixture'}})
 def tearDown(self):
  self.core.store.close();self.tmp.cleanup()
 def resolve(self,q='茅台报价',user='alice',session='chat-a'):
  return self.entities.resolve(user,session,q)
 def confirm(self,r,index=0):
  choices={m['mention_id']:m['candidates'][index]['entity_id'] for m in r['mentions'] if m['candidates']}
  return self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],choices,'native-call')
 def test_name_code_alias_multi_company(self):
  r=self.resolve('比较茅台和平安银行');self.assertEqual(len(r['mentions']),2)
  self.assertEqual({c['entity_type_code'] for c in r['mentions'][0]['candidates']},{'ENTITY_01_01','ENTITY_02_01'})
  self.assertEqual(len(self.resolve('600519报价')['mentions']),1)
 def test_unconfirmed_cannot_create(self):
  with self.assertRaises(Invalid):self.core.create('alice',{'request_key':'test-key','goal':'研究','scope':{'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'},'contact_note':'查看'})
 def test_confirmation_isolated_and_expiring(self):
  r=self.resolve();receipt=self.confirm(r);c=receipt['confirmations'][0]
  self.entities.validate('alice','chat-a',c['confirmation_id'],c['entity_id'])
  for user,session in [('bob','chat-a'),('alice','chat-b')]:
   with self.assertRaises(Invalid):self.entities.validate(user,session,c['confirmation_id'],c['entity_id'])
  self.now+=3601
  with self.assertRaises(Invalid):self.entities.validate('alice','chat-a',c['confirmation_id'],c['entity_id'])
 def test_reselect_revokes_old(self):
  r=self.resolve('平安');a=self.confirm(r)['confirmations'][0]
  self.confirm(r,1)
  with self.assertRaises(Invalid):self.entities.validate('alice','chat-a',a['confirmation_id'],a['entity_id'])
 def test_unknown_failure_and_pronouns(self):
  self.assertFalse(self.resolve('未知股份')['mentions'])
  self.assertFalse(self.resolve('它呢')['mentions'])
  self.confirm(self.resolve());r=self.resolve('它的报价呢');self.assertEqual(r['mentions'][0]['raw_text'],'它')
  self.assertFalse(self.resolve('它呢',session='chat-b')['mentions'])
  bad=EntityConfirmation(self.repo,directory=lambda:{'status':'unavailable','rows':[],'source':{}})
  self.assertEqual(bad.resolve('alice','chat-a','茅台')['provider_status'],'unavailable')
 def test_forged_selection_and_stale_snapshot(self):
  r=self.resolve();m=r['mentions'][0]['mention_id']
  with self.assertRaises(Invalid):self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{m:'SEC:CN:A:999999'},'fake')
  with self.assertRaises(Invalid):self.entities.confirm('alice','chat-b',r['snapshot_id'],r['version'],{},'fake')
 def create_body(self,c):
  return {'request_key':'confirmed-create','goal':'明确委托报价','scope':{'entity_id':c['entity_id'],'exchange':'SSE','operation':'quote_snapshot'},'contact_note':'产品查看','session_id':'chat-a','confirmation_id':c['confirmation_id']}
 def security(self):
  r=self.resolve();m=r['mentions'][0]
  return self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{m['mention_id']:'SEC:CN:A:600519'},'native-test')['confirmations'][0]
 def test_create_replay_after_expiry_and_restart(self):
  c=self.security();body=self.create_body(c);m=self.core.create('alice',body)
  self.now+=3601;self.core.store.close();self.core=Mandates(self.repo,'test')
  self.assertEqual(self.core.create('alice',body)['mandate']['mandate_id'],m['mandate']['mandate_id'])
  with self.assertRaises(Invalid):self.core.create('alice',body|{'request_key':'another-request'})
 def test_revision_requires_confirmation_only_for_object_change(self):
  c=self.security();m=self.core.create('alice',self.create_body(c));mid=m['mandate']['mandate_id']
  body={'request_key':'revise-key','expected_revision':1,'expected_generation':0,'goal':'新问题','scope':m['revision']['scope'],'contact_note':'新约定'}
  changed=body|{'scope':{'entity_id':'SEC:CN:A:000001','exchange':'SZSE','operation':'quote_snapshot'}}
  with self.assertRaises(Invalid):self.core.command('alice',mid,'revise',changed)
  self.assertEqual(self.core.command('alice',mid,'revise',body)['mandate']['current_revision'],2)
 def test_multiple_prior_objects_never_choose_first(self):
  self.confirm(self.resolve('比较茅台和平安银行'))
  r=self.resolve('它的情况');self.assertEqual(r['mentions'][0]['resolution_status'],'ambiguous');self.assertIsNone(r['mentions'][0]['resolved_entity_id'])
 def test_company_identity_has_explicit_bounded_mapping(self):
  r=self.resolve('茅台公司');m=r['mentions'][0]
  c=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{m['mention_id']:'CO:CN:A:600519'},'native-company')['confirmations'][0]
  self.assertEqual(c['operations'],['company_profile','financial_summary'])
  self.entities.validate('alice','chat-a',c['confirmation_id'],'SEC:CN:A:600519','company_profile')
  with self.assertRaises(Invalid):self.entities.validate('alice','chat-a',c['confirmation_id'],'SEC:CN:A:600519','quote_snapshot')
 def test_expired_snapshot_and_wrong_version_rejected(self):
  r=self.resolve()
  with self.assertRaises(Invalid):self.entities.snapshot('alice','chat-a',r['snapshot_id'],'changed-version')
  self.now+=3601
  with self.assertRaises(Invalid):self.confirm(r)
 def test_confirmation_is_durable_but_not_a_mandate(self):
  c=self.security();self.assertEqual(self.core.list('alice')['items'],[])
  self.core.store.close();self.core=Mandates(self.repo,'test')
  self.assertEqual(self.core.entities.current('alice','chat-a')[0]['confirmation_id'],c['confirmation_id'])
 def test_partial_choice_and_all_or_nothing_validation(self):
  r=self.resolve('茅台和平安银行');m=r['mentions'][0]
  with self.assertRaises(Invalid):self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{m['mention_id']:m['candidates'][0]['entity_id'],'forged':'bad'},'call')
  self.assertEqual(self.entities.current('alice','chat-a'),[])
 def test_old_mandate_lifecycle_without_new_confirmation(self):
  from huohuo.research_partner.commands import MandateCreateRequest
  with self.core.store.transaction():
   view=self.core.service.create(self.core.context('alice'),MandateCreateRequest(goal='历史委托',scope={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'},subjects=[{'entity_id':'SEC:CN:A:600519'}],basis={},idempotency_key='legacy-create'))
   mid=view['mandate']['mandate_id'];self.core.store._connect().execute('INSERT INTO mandate_generation VALUES (?,0)',(mid,))
  result=self.core.command('alice',mid,'pause',{'request_key':'legacy-pause','expected_revision':1,'expected_generation':0})
  self.assertEqual(result['mandate']['status'],'paused')
 def test_model_mentions_only_supply_text_not_identity(self):
  e=EntityConfirmation(self.repo,directory=lambda:{'status':'ok','rows':[{'code':'600519','name':'贵州茅台'}],'source':{}})
  r=e.resolve('alice','chat-a','比较茅台与未知公司',['茅台','未知公司'])
  self.assertEqual(len(r['mentions']),2);self.assertTrue(r['mentions'][0]['candidates']);self.assertEqual(r['mentions'][1]['candidates'],[])
  with self.assertRaises(Invalid):e.resolve('alice','chat-a','茅台',['平安银行'])
 def test_unique_reference_reuses_receipt_and_reselection_invalidates_snapshot(self):
  c=self.security();r=self.resolve('它的报价');self.assertFalse(r['requires_confirmation']);self.assertEqual(r['mentions'][0]['confirmation']['confirmation_id'],c['confirmation_id'])
  original=self.resolve('茅台报价');m=original['mentions'][0]
  self.entities.confirm('alice','chat-a',original['snapshot_id'],original['version'],{m['mention_id']:'CO:CN:A:600519'},'change-company')
  with self.assertRaises(Invalid):self.entities.snapshot('alice','chat-a',r['snapshot_id'],r['version'])
 def test_recognized_theme_cannot_be_executed_as_stock(self):
  r=self.resolve('人形机器人');c=self.confirm(r)['confirmations'][0]
  self.assertEqual(c['operations'],[])
  with self.assertRaises(Invalid):self.core.create('alice',self.create_body(c))
 def test_existing_public_search_fallback_is_composed(self):
  from unittest.mock import patch
  from huohuo.research_entities.resolution import directory
  from huohuo.research_entities import security_search
  security_search.reset_cache()
  with patch.object(security_search,'search',return_value={'status':'ok','candidates':[{'code':'600519','name':'贵州茅台'}],'source':{'provider':'东方财富证券搜索'}}):
   result=directory('研究茅台',['茅台'])
  self.assertEqual(result['status'],'ok');self.assertIn('茅台',result['rows'][0]['aliases'])
