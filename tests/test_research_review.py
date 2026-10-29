"""研究建议按当前已确认画像校准；复用证据台账，不写投资事实或交易。"""
import copy
import tempfile
import unittest
from pathlib import Path
from huohuo.contracts import Invalid, canonical
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates
from huohuo.investment.service import Investment
from huohuo.research_entities.confirmation import EntityConfirmation
from huohuo.research_review import ResearchReview, ROLES


class ResearchReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name)/'db.sqlite', clock=lambda: 1793192400)
        self.core = Mandates(self.repo, 'test')
        self.inv = Investment(self.core.store)
        self.entities = EntityConfirmation(self.repo, directory=lambda: {'status':'ok', 'rows':[
            {'code':'600519','name':'合成研究公司'}, {'code':'000001','name':'另一公司'}], 'source':{'provider':'fixture'}})
        snap = self.entities.resolve('alice','chat','合成研究公司股票')
        self.cid = self.entities.confirm('alice','chat',snap['snapshot_id'],snap['version'],
            {snap['mentions'][0]['mention_id']:'SEC:CN:A:600519'},'native')['confirmations'][0]['confirmation_id']
        self.review = ResearchReview(self.repo,self.entities,self.inv)
        self.evidence()

    def tearDown(self):
        self.core.store.close()
        self.tmp.cleanup()

    def evidence(self, status='ok', principal='alice', session='chat', cid=None):
        with self.repo.connection(True) as db:
            db.execute('INSERT OR REPLACE INTO research_tool_calls VALUES(?,?,?,?,?,?,?,?,?)',
                ('source',principal,session,'fixture','financials_lookup','hash',canonical({'confirmation_id':cid or self.cid}),
                 canonical({'status':status,'source':'synthetic','data':{'metrics':[]}}),self.repo.clock()))

    def profile(self, aggressive=False):
        p = self.inv.preview('alice', {'command':'risk_profile','payload':{'tier':'quick','answers':[
            {'qid':'horizon','option':4 if aggressive else 0},
            {'qid':'loss_tolerance','option':4 if aggressive else 0},
            {'qid':'goal','option':4 if aggressive else 0}]}})
        self.inv.commit('alice',{'preview_id':p['preview_id'],'request_key':p['preview_id']})

    def arguments(self):
        return {'confirmation_id':self.cid,'signal':{'action':'买入','risk_score':.8,'confidence':.7,'target_price':120.,'reasoning':'合成研究判断'},
            'perspectives':[{'role':r,'summary':'合成论点','evidence_ids':['source']} for r in ROLES]}

    def test_server_profile_calibrates_and_preserves_original_evidence_and_facts(self):
        self.profile()
        before = self.inv.read('alice')
        args = self.arguments()
        result = self.review.run('alice','chat','review',args)
        self.assertEqual(result['original_signal']['action'],'买入')
        self.assertEqual(result['effective_signal']['action'],'持有')
        self.assertEqual(result['guard_status'],'calibrated')
        self.assertEqual(result['risk_profile']['profile'],'conservative')
        self.assertEqual(result['coverage']['status'],'complete')
        self.assertEqual(result['evidence_ids'],['source'])
        self.assertEqual(args['signal']['action'],'买入')
        self.assertEqual(self.inv.read('alice'),before)
        self.assertEqual(self.review.history('alice',{})['items'][0],result)
        self.assertEqual(self.review.history('bob',{})['items'],[])
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM mandates').fetchone()[0],0)

    def test_missing_profile_or_score_cannot_be_reported_as_guard_passed(self):
        a=self.arguments()
        r=self.review.run('alice','chat','missing-profile',a)
        self.assertEqual(r['guard_status'],'unknown')
        self.assertIsNone(r['effective_signal'])
        self.profile()
        a['signal']['risk_score']=None
        r=self.review.run('alice','chat','missing-score',a)
        self.assertEqual(r['guard_status'],'unknown')
        a['signal']['action']='无法判断'
        a['perspectives']=[]
        r=self.review.run('alice','chat','missing-material',a)
        self.assertEqual(r['coverage']['status'],'incomplete')
        self.assertEqual(set(r['coverage']['missing_roles']),set(ROLES))

    def test_replay_returns_original_profile_snapshot_not_today_profile(self):
        self.profile()
        a=self.arguments();r=self.review.run('alice','chat','same',a)
        self.profile(aggressive=True)
        self.assertEqual(self.review.run('alice','chat','same',a),r)
        newer=self.review.run('alice','chat','new',a)
        self.assertEqual(newer['effective_signal']['action'],'买入')
        self.assertEqual(newer['guard_status'],'unchanged')
        a['signal']['risk_score']=.1
        with self.assertRaises(Conflict):self.review.run('alice','chat','same',a)

    def test_evidence_requires_owner_session_subject_and_success(self):
        a=self.arguments()
        for status,owner,session,cid in [('unavailable','alice','chat',None),('ok','bob','chat',None),
                ('ok','alice','other',None),('ok','alice','chat','missing')]:
            self.evidence(status,owner,session,cid)
            with self.subTest(status=status,owner=owner,session=session,cid=cid),self.assertRaises(Invalid):
                self.review.run('alice','chat','bad-source',a)
        self.evidence()
        with self.assertRaises(Invalid):self.review.run('alice','other','other-session',a)

    def test_strict_model_input_and_unknown_never_default_to_hold(self):
        a=self.arguments()
        for risk in [True,-.1,1.1,float('nan'),'0.3']:
            bad=copy.deepcopy(a);bad['signal']['risk_score']=risk
            with self.assertRaises(Invalid):self.review.run('alice','chat','bad',bad)
        for extra in ['principal','profile','trade_date','authorized']:
            with self.assertRaises(Invalid):self.review.run('alice','chat','bad',{**a,extra:'forged'})
        a['perspectives'][0]['evidence_ids']=[]
        self.profile()
        r=self.review.run('alice','chat','partial',a)
        self.assertEqual(r['coverage']['status'],'incomplete')
        self.assertIn('fundamentals',r['coverage']['unverified_roles'])

    def test_shared_research_rate_bound_preserves_replay_and_bounded_source_metadata(self):
        with self.repo.connection(True) as db:
            db.execute('UPDATE research_tool_calls SET result=? WHERE id=?',
                (canonical({'status':'ok','source':'合成来源'*2000,'data':{}}),'source'))
        a=self.arguments()
        first=self.review.run('alice','chat','rate0',a)
        self.assertLessEqual(len(first['evidence_refs'][0]['source']),500)
        for i in range(1,19):self.review.run('alice','chat','rate'+str(i),a)
        with self.assertRaises(Invalid):self.review.run('alice','chat','over-rate',a)
        self.assertEqual(self.review.run('alice','chat','rate0',a),first)
