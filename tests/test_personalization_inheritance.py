import json
import tempfile
import time
import unittest
from pathlib import Path
from huohuo.execution import Repository, Conflict, Missing, digest
from huohuo.mandates import Mandates
from huohuo.personalization.service import Personalization
from huohuo.contracts import Invalid,canonical

class PersonalizationTest(unittest.TestCase):
    def test_chat_interaction_uses_same_learning_switch_with_distinct_surface(self):
        cid=self.svc.read('owner')['cards']['cards'][0]['card_id']
        body={'request_key':'chat-event','session_id':'chat-context','card_id':cid,'action':'analyze','surface':'assistant'}
        self.assertEqual(self.svc.record('owner',body)['ignored'],1)
        self.enable();body['request_key']='chat-enabled'
        result=self.svc.record('owner',body)
        self.assertEqual(result['stored'],1)
        self.assertEqual(self.svc.record('owner',body),result)
        _,saved=self.svc.repo.load('owner')
        self.assertEqual(saved['behavior']['events'][0]['surface'],'assistant')
        self.assertEqual(saved['behavior']['events'][0]['action'],'analyze')
        self.assertEqual(saved['behavior']['events'][0]['context']['ticker'],'600519')
        for field in ['principal','timestamp','context']:
            with self.assertRaises(Invalid):self.svc.record('owner',{**body,field:'forged'})
        with self.assertRaises(Invalid):self.svc.record('owner',{**body,'request_key':'bad-surface','surface':'arbitrary'})
    def test_matching_inherits_explainable_scores_and_interest_never_changes_risk(self):
        from huohuo.strategies.storage import Documents
        docs=Documents(self.core.store,'owner')
        docs.set('strategies','s1',{'id':'s1','name':'合成合格策略','status':'active','kind':'ma_cross','direction':'利好','symbols':['600519'],'params':{},'out_of_sample':{}})
        value=self.svc.read('owner')
        item=value['matches']['items'][0]
        self.assertEqual(item['strategy_id'],'s1')
        self.assertIn('profile_fit',item['breakdown'])
        self.assertTrue(item['match_reasons'][0]['text'])
        self.assertFalse(value['profile_is_explicit'])
        self.assertIsNone(self.core.investment.read('owner')['risk_profile'])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.repo=Repository(Path(self.tmp.name)/'db.sqlite')
        self.core=Mandates(self.repo,'test')
        self.svc=Personalization(self.core.store)
        self.event={'id':'evt-test','source':'synthetic','observed_at':time.time(),'title':'合成持仓事件','summary':'受控来源，不是真实事件',
                    'securities':[{'code':'600519','name':'合成公司','exchange':'SSE'}],'evidence_ref':'synthetic:1'}
        self.core.store._connect().execute('INSERT INTO strategy_events VALUES(?,?,?,?,?)',('owner',self.event['id'],digest(self.event),canonical(self.event),self.event['observed_at']))
    def tearDown(self):self.core.store.close();self.tmp.cleanup()
    def save(self,p):return self.svc.commit('owner',{'preview_id':p['preview_id'],'request_key':p['preview_id']})
    def enable(self):return self.save(self.svc.preview('owner',{'action':'learning','enabled':True}))
    def test_reuse_cards_feedback_pause_clear_and_persistence(self):
        read=self.svc.read('owner')
        self.assertFalse(read['learning']['enabled'])
        self.assertEqual(read['cards']['total'],1)
        card=read['cards']['cards'][0]
        self.assertEqual(card['title'],'合成持仓事件')
        body={'request_key':'read:1','session_id':'session','card_id':card['card_id'],'action':'open'}
        self.assertEqual(self.svc.record('owner',body)['ignored'],1)
        self.enable()
        body['request_key']='read:2'
        r=self.svc.record('owner',body)
        self.assertEqual(r['stored'],1)
        self.assertEqual(self.svc.record('owner',body),r)
        self.save(self.svc.preview('owner',{'action':'feedback','card_id':card['card_id'],'sentiment':'useful'}))
        read=Personalization(self.core.store).read('owner')
        self.assertEqual(read['learning']['event_count'],1)
        self.assertEqual(read['learning']['feedback_count'],1)
        self.assertEqual(read['cards']['cards'][0]['feedback_sentiment'],'useful')
        self.assertEqual(read['profile']['behavior']['aggression_delta'],0)
        self.assertEqual(self.svc.read('other')['learning']['record_count'],0)
        self.save(self.svc.preview('owner',{'action':'learning','enabled':False}))
        body['request_key']='read:3'
        self.assertEqual(self.svc.record('owner',body)['ignored'],1)
        p=self.svc.preview('owner',{'action':'clear'})
        self.assertEqual(self.svc.read('owner')['learning']['record_count'],2)
        result=self.save(p)
        self.assertEqual(self.save(p),result)
        self.assertEqual(self.svc.read('owner')['learning']['record_count'],0)
        self.assertIsNone(self.core.investment.read('owner')['risk_profile'])
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM mandates').fetchone()[0],0)
    def test_preview_is_owner_bound_conflicts_and_unknown_card_not_fabricated(self):
        p=self.svc.preview('owner',{'action':'learning','enabled':True})
        with self.assertRaises(Missing):self.svc.inspect('other',p['preview_id'])
        self.enable()
        with self.assertRaises(Conflict):self.save(p)
        with self.assertRaises(Invalid):self.svc.preview('owner',{'action':'feedback','card_id':'card-invented','sentiment':'useful'})
        with self.assertRaises(Invalid):self.svc.record('owner',{'request_key':'r','session_id':'s','card_id':'fake','action':'open'})
    def test_feedback_is_last_explicit_value_and_neutral_removes(self):
        self.enable();cid=self.svc.read('owner')['cards']['cards'][0]['card_id']
        for sentiment,count in [('useful',1),('useless',1),('neutral',0)]:
            self.save(self.svc.preview('owner',{'action':'feedback','card_id':cid,'sentiment':sentiment}))
            self.assertEqual(self.svc.read('owner')['learning']['feedback_count'],count)
    def test_atomic_failure_preserves_state_and_no_receipt(self):
        p=self.svc.preview('owner',{'action':'learning','enabled':True})
        self.core.store._connect().execute("CREATE TRIGGER fail_personal BEFORE INSERT ON personalization_audit BEGIN SELECT RAISE(ABORT,'fail'); END")
        with self.assertRaises(Exception):self.save(p)
        self.assertFalse(self.svc.read('owner')['learning']['enabled'])
        self.assertIsNone(self.svc.inspect('owner',p['preview_id']).get('receipt'))
    def test_clear_removes_derived_traces_and_old_preview_cannot_restore_learning(self):
        old=self.svc.preview('owner',{'action':'learning','enabled':True});self.save(old)
        cid=self.svc.read('owner')['cards']['cards'][0]['card_id']
        self.save(self.svc.preview('owner',{'action':'feedback','card_id':cid,'sentiment':'useful'}))
        pending=self.svc.preview('owner',{'action':'feedback','card_id':cid,'sentiment':'useless'})
        current=self.svc.preview('owner',{'action':'clear'});self.save(current)
        db=self.core.store._connect()
        self.assertEqual(db.execute("SELECT count(*) FROM personalization_audit WHERE principal='owner' AND action IN ('reading','feedback')").fetchone()[0],0)
        self.assertEqual(db.execute("SELECT count(*) FROM personalization_receipts WHERE principal='owner'").fetchone()[0],1)
        self.assertEqual(db.execute("SELECT count(*) FROM personalization_previews WHERE principal='owner'").fetchone()[0],1)
        with self.assertRaises(Missing):self.svc.inspect('owner',pending['preview_id'])
        self.assertTrue(self.svc.read('owner')['learning']['enabled'])
        self.assertEqual(self.svc.read('owner')['learning']['record_count'],0)
