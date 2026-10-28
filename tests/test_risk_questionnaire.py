import tempfile
import unittest
from pathlib import Path
from huohuo.execution import Repository, Conflict, Missing
from huohuo.mandates import Mandates
from huohuo.contracts import Invalid
from huohuo.investment.service import Investment


class RiskQuestionnaireTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name)/'db.sqlite')
        self.core = Mandates(self.repo, 'test')
        self.inv = Investment(self.core.store)

    def tearDown(self):
        self.core.store.close(); self.tmp.cleanup()

    def body(self, tier='quick', option=0):
        bank = self.inv.read('owner')['risk_questionnaire']
        return {'command': 'risk_profile', 'payload': {'tier': tier, 'answers': [
            {'qid': q['qid'], 'option': option} for q in bank[tier]]}}

    def commit(self, preview):
        return self.inv.commit('owner', {'preview_id': preview['preview_id'], 'request_key': preview['preview_id']})

    def test_preview_cancel_save_read_history_and_restart(self):
        self.assertIsNone(self.inv.read('owner')['risk_profile'])
        p = self.inv.preview('owner', self.body())
        self.assertEqual(p['after']['risk_profile']['profile'], 'conservative')
        self.assertEqual(self.inv.read('owner')['version'], 0)  # exit without commit
        result = self.commit(p)
        self.assertEqual(self.commit(p), result)
        current = Investment(self.core.store).read('owner')
        self.assertEqual(current['risk_profile']['score'], 3)
        self.assertTrue(current['risk_profile']['recorded_at'])
        self.assertEqual(self.inv.snapshot('owner', 1)['risk_profile'], current['risk_profile'])
        self.commit(self.inv.preview('owner', self.body('full', 4)))
        self.assertEqual(self.inv.read('owner')['risk_profile']['score'], 40)
        self.assertEqual(len(self.inv.read('owner')['risk_profile_history']), 2)
        self.assertEqual(self.inv.snapshot('owner', 1)['risk_profile']['score'], 3)

    def test_no_holdings_authorization_or_outbox_side_effect(self):
        self.commit(self.inv.preview('owner', self.body()))
        current = self.inv.read('owner')
        self.assertEqual(current['holdings_status'], 'not_recorded')
        self.assertEqual(current['watchlist_status'], 'not_recorded')
        self.assertEqual(current['holdings'], [])
        db = self.core.store._connect()
        for table in ('investment_outbox', 'mandates', 'research_jobs'):
            self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0], 0)

    def test_exact_bank_options_not_model_scores_or_duplicate_answers(self):
        import copy
        original = self.body()
        cases = []
        for value in (-1, 5, True, 1.5, '2'):
            body = copy.deepcopy(original); body['payload']['answers'][0]['option'] = value; cases.append(body)
        body = copy.deepcopy(original); body['payload']['answers'][0]['score'] = 5; cases.append(body)
        body = copy.deepcopy(original); body['payload']['answers'].pop(); cases.append(body)
        body = copy.deepcopy(original); body['payload']['answers'][1] = body['payload']['answers'][0]; cases.append(body)
        body = copy.deepcopy(original); body['payload']['tier'] = 'unknown'; cases.append(body)
        for body in cases:
            with self.subTest(body=body), self.assertRaises(Invalid): self.inv.preview('owner', body)
        self.assertEqual(self.inv.read('owner')['version'], 0)

    def test_owner_conflict_and_atomic_rollback(self):
        p = self.inv.preview('owner', self.body())
        with self.assertRaises(Missing): self.inv.inspect_preview('other', p['preview_id'])
        self.commit(self.inv.preview('owner', self.body('full', 4)))
        with self.assertRaises(Conflict): self.commit(p)
        self.assertIsNone(self.inv.read('other')['risk_profile'])
        p = self.inv.preview('owner', self.body())
        self.core.store._connect().execute("CREATE TRIGGER fail_kyc BEFORE INSERT ON investment_audit BEGIN SELECT RAISE(ABORT,'fail'); END")
        with self.assertRaises(Exception): self.commit(p)
        self.assertEqual(self.inv.read('owner')['version'], 1)
        self.assertEqual(self.inv.read('owner')['risk_profile']['score'], 40)

    def test_normal_fact_edit_preserves_preference_and_history(self):
        self.commit(self.inv.preview('owner', self.body()))
        prior = self.inv.read('owner')['risk_profile']
        p = self.inv.preview('owner', {'command': 'watchlist', 'payload': {
            'ticker': '600519', 'name': '贵州茅台', 'reason': '合成验收', 'remove': False}})
        self.commit(p)
        self.assertEqual(self.inv.read('owner')['risk_profile'], prior)
        self.assertEqual(len(self.inv.read('owner')['risk_profile_history']), 1)

    def test_scoring_matches_legacy_band_boundaries(self):
        from huohuo.investment.risk_questionnaire import score
        for tier, totals in [('quick', {7: 'conservative', 8: 'balanced', 11: 'balanced', 12: 'aggressive'}),
                             ('full', {18: 'conservative', 19: 'balanced', 29: 'balanced', 30: 'aggressive'})]:
            for total, expected in totals.items():
                body = self.body(tier); answers = body['payload']['answers']
                remaining = total - len(answers)
                for a in answers:
                    a['option'] = min(4, remaining); remaining -= a['option']
                self.assertEqual(score(body['payload'])['profile'], expected)
