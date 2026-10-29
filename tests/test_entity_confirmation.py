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
  choices={m['subject_id']:m['candidates'][index]['entity_id'] for m in r['discussion_subjects'] if m['candidates']}
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
  self.assertEqual(c['operations'],['company_profile','financial_summary','news'])
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
  original=self.resolve('茅台公司');m=original['mentions'][0]
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

 def test_same_entity_name_code_is_one_subject_scope_and_receipt(self):
  r=self.resolve('平安银行 000001 即时行情核对')
  self.assertEqual(len(r['mentions']),2)
  self.assertEqual(len(r['discussion_subjects']),1)
  g=r['discussion_subjects'][0]
  self.assertEqual(g['primary_entity_id'],'SEC:CN:A:000001')
  self.assertEqual(len(g['mention_ids']),2)
  self.assertEqual([c['entity_id'] for c in g['candidates']],['SEC:CN:A:000001'])
  self.assertEqual(len(r['entity_list']),1)
  saved=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{g['subject_id']:g['primary_entity_id']},'native-group')
  self.assertEqual(len(saved['confirmations']),1)
  self.assertEqual(len(self.entities.current('alice','chat-a')),1)
  c=saved['confirmations'][0]
  self.assertEqual(set(c['mention_ids']),set(g['mention_ids']))
  for query in ('平安银行报价','000001报价','它的报价'):
   again=self.resolve(query)
   self.assertFalse(again['requires_confirmation'])
   self.assertEqual(again['discussion_subjects'][0]['confirmation']['confirmation_id'],c['confirmation_id'])
 def test_subjects_do_not_merge_ambiguous_candidates_or_distinct_entities(self):
  r=self.resolve('比较平安与平安银行')
  self.assertEqual(len(r['discussion_subjects']),2)
  self.assertTrue(r['requires_confirmation'])
  r=self.resolve('平安银行 000001 和贵州茅台 600519 报价')
  self.assertEqual(len(r['discussion_subjects']),2)
  self.assertEqual(len(r['entity_list']),2)
 def test_group_choice_is_validated_and_alias_reselection_revokes_old(self):
  r=self.resolve('平安银行 000001 报价');g=r['discussion_subjects'][0]
  with self.assertRaises(Invalid):
   self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{g['subject_id']:'CO:CN:A:000001'},'forged-related')
  c=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{g['subject_id']:g['primary_entity_id']},'group')['confirmations'][0]
  reused=self.resolve('000001报价')
  change=self.resolve('平安银行公司');other=change['discussion_subjects'][0]
  self.entities.confirm('alice','chat-a',change['snapshot_id'],change['version'],{other['subject_id']:'CO:CN:A:000001'},'reselect')
  with self.assertRaises(Invalid):self.entities.validate('alice','chat-a',c['confirmation_id'],c['entity_id'])
  with self.assertRaises(Invalid):self.entities.snapshot('alice','chat-a',reused['snapshot_id'],reused['version'])
  quote=self.resolve('000001报价')
  self.assertTrue(quote['requires_confirmation'])
 def test_duplicate_group_choices_reject_conflicts_and_do_not_duplicate_receipts(self):
  r=self.resolve('平安银行 000001 报价');g=r['discussion_subjects'][0]
  choices={mid:g['primary_entity_id'] for mid in g['mention_ids']}
  saved=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],choices,'compat')
  self.assertEqual(len(saved['confirmations']),1)
  repeated=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],choices,'compat')
  self.assertEqual(saved['confirmations'],repeated['confirmations'])
 def test_name_code_conflict_requires_one_explicit_choice_not_reused(self):
  self.security()
  r=self.resolve('平安银行 600519 行情');g=r['discussion_subjects'][0]
  self.assertEqual(len(r['discussion_subjects']),1)
  self.assertEqual(g['merge_reason'],'name_code_conflict')
  self.assertTrue(r['requires_confirmation']);self.assertEqual(r['status'],'pending_clarification')
  self.assertIsNone(r['entity_list'][0]['entity_id'])
  c=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{g['subject_id']:'SEC:CN:A:600519'},'conflict-choice')['confirmations'][0]
  self.assertNotIn('平安银行',c['mention_texts'])
  self.assertTrue(self.resolve('平安银行行情')['requires_confirmation'])
 def test_legacy_snapshot_remains_answerable_without_new_groups(self):
  from huohuo.contracts import canonical
  r=self.resolve('茅台报价')
  r.pop('discussion_subjects');r.pop('confirmation_protocol')
  with self.repo.connection(True) as db:
   db.execute('UPDATE entity_snapshots SET payload=? WHERE id=?',(canonical(r),r['snapshot_id']))
  m=r['mentions'][0]
  saved=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{m['mention_id']:'SEC:CN:A:600519'},'old-question')
  self.assertEqual(len(saved['confirmations']),1)
  self.assertNotIn('subject_id',saved['confirmations'][0])
 def test_equal_code_different_entity_namespace_is_not_identity(self):
  from huohuo.research_entities.models import EntityMention,EntityCandidate
  from huohuo.research_entities.subjects import discussion_subjects
  mentions=[]
  for i,(eid,kind) in enumerate([('SEC:CN:A:000001','ENTITY_01_01'),('INDEX:CN:SSE:000001','ENTITY_01_03')]):
   mentions.append(EntityMention(mention_id=str(i),raw_text='000001',start_offset=i*7,end_offset=i*7+6,resolution_status='resolved',resolved_entity_id=eid,candidate_entity_ids=[eid],candidates=[EntityCandidate(entity_id=eid,entity_type_code=kind,confidence=1)]))
  self.assertEqual(len(discussion_subjects(mentions)),2)
 def test_group_partial_confirmation_and_other_subject_survives_reselect(self):
  r=self.resolve('平安银行 000001 和贵州茅台 600519 报价')
  a,b=r['discussion_subjects']
  self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{a['subject_id']:a['primary_entity_id']},'partial')
  again=self.resolve('平安银行 000001 和贵州茅台 600519 报价')
  self.assertIn('confirmation',again['discussion_subjects'][0]);self.assertNotIn('confirmation',again['discussion_subjects'][1])
  saved=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{b['subject_id']:b['primary_entity_id']},'other')['confirmations'][0]
  change=self.resolve('平安银行公司');s=change['discussion_subjects'][0]
  self.entities.confirm('alice','chat-a',change['snapshot_id'],change['version'],{s['subject_id']:s['primary_entity_id']},'change')
  self.entities.validate('alice','chat-a',saved['confirmation_id'],saved['entity_id'])
 def test_alias_without_new_task_intent_reuses_identity_not_company_permissions(self):
  r=self.resolve('平安银行 000001 行情');g=r['discussion_subjects'][0]
  c=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{g['subject_id']:g['primary_entity_id']},'select')['confirmations'][0]
  for query in ('000001呢','平安银行呢'):
   again=self.resolve(query)
   self.assertFalse(again['requires_confirmation'])
   self.assertEqual(again['discussion_subjects'][0]['confirmation']['confirmation_id'],c['confirmation_id'])
  self.assertTrue(self.resolve('平安银行公司')['requires_confirmation'])
 def test_user_selecting_same_entity_from_two_ambiguous_groups_saves_one_receipt(self):
  r=self.resolve('平安与平安')
  self.assertEqual(len(r['discussion_subjects']),2)
  choices={s['subject_id']:'CO:CN:A:000001' for s in r['discussion_subjects']}
  c=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],choices,'select-same')
  self.assertEqual(len(c['confirmations']),1)
  self.assertEqual(len(c['confirmations'][0]['mention_ids']),2)
  self.assertEqual(len(self.entities.current('alice','chat-a')),1)
 def test_explicit_company_and_security_are_related_but_separate_subjects(self):
  r=self.resolve('比较平安银行公司和平安银行股票')
  self.assertEqual(len(r['discussion_subjects']),2)
  self.assertEqual({s['primary_entity_id'] for s in r['discussion_subjects']},{'CO:CN:A:000001','SEC:CN:A:000001'})
  c=self.confirm(r)
  self.assertEqual(len(c['confirmations']),2)
  for receipt in c['confirmations']:
   self.entities.validate('alice','chat-a',receipt['confirmation_id'],receipt['entity_id'])
 def test_partial_then_combined_same_choice_preserves_all_member_evidence(self):
  r=self.resolve('平安与平安');a,b=r['discussion_subjects']
  first=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{a['subject_id']:'CO:CN:A:000001'},'partial')
  combined=self.entities.confirm('alice','chat-a',r['snapshot_id'],r['version'],{a['subject_id']:'CO:CN:A:000001',b['subject_id']:'CO:CN:A:000001'},'both')
  self.assertEqual(len(combined['confirmations']),1)
  self.assertEqual(len(combined['confirmations'][0]['mention_ids']),2)
  self.assertEqual(len(self.entities.current('alice','chat-a')),1)
 def test_exchange_qualified_code_is_same_entity_with_original_offsets(self):
  for fragments in (None,['平安银行','000001.SZ']):
   query='平安银行（000001.SZ）的行情'
   r=self.entities.resolve('alice','chat-a',query,fragments)
   self.assertEqual(len(r['discussion_subjects']),1)
   self.assertEqual(len(r['mentions']),2)
   code=r['mentions'][1]
   self.assertEqual(code['raw_text'],'000001.SZ')
   self.assertEqual(query[code['start_offset']:code['end_offset']],'000001.SZ')
   self.assertEqual(r['discussion_subjects'][0]['primary_entity_id'],'SEC:CN:A:000001')
  wrong=self.resolve('平安银行 000001.SH 行情')
  self.assertEqual(len(wrong['discussion_subjects']),2)
  self.assertFalse(wrong['mentions'][1]['candidates'])
  self.assertTrue(wrong['requires_confirmation'])
 def test_qualified_code_directory_uses_canonical_code_not_full_suffix(self):
  from unittest.mock import patch
  from huohuo.research_entities.resolution import directory
  from huohuo.research_entities import security_search
  security_search.reset_cache()
  with patch.object(security_search,'search',return_value={'status':'ok','candidates':[{'code':'000001','name':'平安银行'}],'source':{'provider':'东方财富证券搜索'}}) as lookup:
   result=directory('平安银行 000001.SZ 行情',['000001.SZ'])
   lookup.assert_called_once_with('000001')
   self.assertEqual(result['status'],'ok')
