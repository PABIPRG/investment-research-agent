"""旧偏好资产在同一投资事实中的行为回归，不读取旧账户。"""
import copy
from test_risk_questionnaire import RiskQuestionnaireTest
from huohuo.contracts import Invalid


class RiskInheritanceTest(RiskQuestionnaireTest):
    def test_manual_adjust_preserves_inferred_answers_and_versions_budget(self):
        self.commit(self.inv.preview('owner', self.body()))
        original = self.inv.read('owner')['risk_profile']
        p = self.inv.preview('owner', {'command': 'risk_adjust', 'payload': {
            'risk_tolerance': 1.0, 'horizon_years': 1}})
        self.assertEqual(p['after']['risk_profile']['profile'], 'balanced')
        self.assertEqual(self.inv.read('owner')['risk_profile'], original)
        self.commit(p)
        current = self.inv.read('owner')
        r = current['risk_profile']
        self.assertEqual(r['inferred_profile'], 'conservative')
        self.assertEqual(r['answers'], original['answers'])
        self.assertEqual(r['score'], original['score'])
        self.assertEqual(r['manual_adjust'], {'risk_tolerance': 1.0, 'horizon_years': 1})
        self.assertEqual(current['risk_policy']['risk_budget']['hhi_max'], .30)
        self.assertEqual(len(current['risk_profile_history']), 2)
        self.assertEqual(self.inv.snapshot('owner', 1)['risk_policy']['risk_budget']['hhi_max'], .20)
        self.assertIsNone(self.inv.read('other')['risk_policy'])
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM mandates').fetchone()[0], 0)

    def test_adjust_requires_explicit_valid_values_and_completed_questionnaire(self):
        good = {'risk_tolerance': .5, 'horizon_years': 3}
        with self.assertRaises(Invalid):
            self.inv.preview('owner', {'command': 'risk_adjust', 'payload': good})
        self.commit(self.inv.preview('owner', self.body()))
        for field, values in [('risk_tolerance', [-.1, 1.1, True, '1', float('nan')]),
                              ('horizon_years', [0, 31, True, 1.5, '3'])]:
            for value in values:
                p = {**good, field: value}
                with self.subTest(p=p), self.assertRaises(Invalid):
                    self.inv.preview('owner', {'command': 'risk_adjust', 'payload': p})

    def test_parser_is_draft_partial_strict_and_owner_state_is_unchanged(self):
        before = copy.deepcopy(self.inv.read('owner'))
        result = self.inv.parse_risk({'tier': 'quick', 'text': '我计划持有五年以上，能接受20%左右亏损，追求长期增值'})
        answers = {x['qid']: x['option'] for x in result['answers']}
        self.assertEqual(answers, {'horizon': 4, 'loss_tolerance': 3, 'goal': 2})
        self.assertEqual(result['missing'], [])
        self.assertEqual(self.inv.read('owner'), before)
        partial = self.inv.parse_risk({'tier': 'full', 'text': '收入稳定'})
        self.assertTrue(partial['missing'])
        self.assertEqual(len(partial['answers']), 1)
        ambiguous = self.inv.parse_risk({'tier': 'quick', 'text': '能接受5%还是20%我没想好'})
        self.assertIn('loss_tolerance', ambiguous['missing'])
        self.assertTrue(ambiguous['warnings'])

    def test_model_candidates_are_validated_untrusted_and_never_scored_as_submitted(self):
        draft = self.inv.parse_risk({'tier': 'quick', 'text': '愿意长期拿着',
                                   'candidates': [{'qid': 'horizon', 'option': 4}]})
        self.assertEqual(draft['answers'][0]['source'], 'dsh_candidate')
        self.assertTrue(draft['requires_confirmation'])
        for option in (True, 8, -1):
            with self.assertRaises(Invalid):
                self.inv.parse_risk({'tier': 'quick', 'text': 'test',
                                    'candidates': [{'qid': 'horizon', 'option': option}]})
        with self.assertRaises(Invalid):
            self.inv.parse_risk({'tier': 'quick', 'text': 'test', 'candidates': [
                {'qid': 'horizon', 'option': 1}, {'qid': 'horizon', 'option': 2}]})
