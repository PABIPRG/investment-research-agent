"""PAB-47/PAB-44：合成来源、真实 SQLite；禁止任何外部请求。"""
import copy
import tempfile
import unittest
from pathlib import Path
from huohuo.contracts import Invalid
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates
from huohuo.research_entities.bounded import collect

SCOPE = {'entity_id': 'SEC:CN:A:600519', 'exchange': 'SSE',
         'operation': 'financial_summary', 'period': '20260630',
         'metric': '营业总收入', 'basis': 'source_abstract'}


class ResearchAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name) / 'business.sqlite')
        self.core = Mandates(self.repo, 'night-test')
        self.core.entities.directory = lambda: {'status': 'ok', 'rows': [
            {'code': '600519', 'name': '贵州茅台'}], 'source': {'provider': 'fixture'}}
        snap = self.core.entities.resolve('alice', 'chat', '600519股票')
        cid = self.core.entities.confirm('alice', 'chat', snap['snapshot_id'], snap['version'],
              {snap['mentions'][0]['mention_id']: SCOPE['entity_id']}, 'fixture')['confirmations'][0]['confirmation_id']
        self.mandate = self.core.create('alice', {'session_id': 'chat', 'confirmation_id': cid,
            'request_key': 'first-research', 'goal': '研究 2026 年半年报营业总收入摘要并保留未知口径',
            'scope': SCOPE, 'contact_note': '仅在产品中查看；没有外发授权'})
        self.core.tick()
        self.job = self.repo.claim('test-worker')

    def tearDown(self):
        self.core.store.close()
        self.tmp.cleanup()

    def document(self, value=123):
        return collect(SCOPE, lambda _: {'code': '600519', 'records': [
            {'指标': '营业总收入', '20260630': value}]})

    def save(self, document):
        return self.repo.save_evidence(self.job['attempt_id'], self.job['lease_token'], document)

    def result(self, evidence, judgement='unknown'):
        return {'status': 'succeeded', 'execution_id': self.job['execution_id'], 'scope': SCOPE,
                'summary': '合成验收摘要；数据来源未注明单位，累计或单季口径未核验，不能判断阈值。',
                'evidence_ids': [evidence['evidence_id']],
                'judgements': {'notable_change': {'judgement': judgement,
                    'reason': '缺少已核验单位和可比口径', 'evidence_refs': [evidence['evidence_id']]}}}

    def finish(self, result):
        return self.repo.finish(self.job['attempt_id'], self.job['lease_token'], result)

    def test_internal_evidence_mismatch_cannot_be_saved(self):
        mutations = [lambda d: d['raw'].update(code='000001'),
                     lambda d: d['values']['records'][0].update({'20260630': 999}),
                     lambda d: d.update(source_hash='0' * 64),
                     lambda d: d['values']['records'][0].update({'指标': '净利润'}),
                     lambda d: d.update(observed_at='not-a-time'),
                     lambda d: d.update(source='invented-source'),
                     lambda d: d.update(source_url='')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                document = copy.deepcopy(self.document())
                mutate(document)
                with self.assertRaises((Conflict, Invalid)):
                    self.save(document)
        self.assertEqual(self.repo.evidence('alice', self.job['execution_id']), [])

    def test_document_cannot_override_program_receipt(self):
        for name in ['evidence_id', 'execution_id', 'attempt_id', 'attempt_status']:
            with self.subTest(name=name), self.assertRaises((Conflict, Invalid)):
                self.save(self.document() | {name: 'forged'})

    def test_missing_or_non_numeric_values_never_become_available(self):
        for value in [None, '', '—', '--', 'N/A', True, {}, [], 'NaN', 'Infinity']:
            with self.subTest(value=value):
                self.assertNotEqual(self.document(value)['status'], 'ok')
        self.assertEqual(self.document(0)['status'], 'ok')

    def test_ambiguous_metric_does_not_select_a_record(self):
        document = collect(SCOPE, lambda _: {'code': '600519', 'records': [
            {'指标': '营业总收入', '20260630': 123}, {'指标': '营业总收入', '20260630': 456}]})
        self.assertEqual(document['status'], 'unavailable')
        self.assertEqual(document['reason'], 'requested_metric_ambiguous')

    def test_unknown_units_cannot_produce_definite_judgement(self):
        evidence = self.save(self.document())
        for verdict in ['met', 'unmet']:
            for nested in [False, True]:
                result = self.result(evidence, verdict)
                if nested:
                    result['contact_suggestion'] = {'judgements': result.pop('judgements')}
                with self.subTest(verdict=verdict, nested=nested), self.assertRaises((Conflict, Invalid)):
                    self.finish(result)
        self.core.tick()
        view = self.core.get('alice', self.mandate['mandate']['mandate_id'])
        self.assertIsNone(view['baseline'])
        self.assertEqual(view['results'], [])

    def test_judgement_cannot_reference_unbound_evidence(self):
        evidence = self.save(self.document())
        result = self.result(evidence)
        result['judgements']['notable_change']['evidence_refs'] = ['another-attempt-evidence']
        with self.assertRaises((Conflict, Invalid)):
            self.finish(result)

    def test_failed_result_cannot_claim_another_scope(self):
        with self.assertRaises((Conflict, Invalid)):
            self.finish({'status': 'failed', 'error': '来源失败', 'scope': SCOPE | {'period': '20260331'}})

    def test_unknown_summary_baseline_is_durable_and_receipt_idempotent(self):
        evidence = self.save(self.document(0))
        result = self.result(evidence)
        receipt = self.finish(result)
        self.core.store.close()
        self.core = Mandates(self.repo, 'night-test')
        self.core.tick()
        self.assertEqual(receipt, self.finish(result))
        self.core.tick()
        view = self.core.get('alice', self.mandate['mandate']['mandate_id'])
        self.assertEqual(view['baseline']['scope'], SCOPE)
        self.assertEqual(view['baseline']['evidence_ids'], [evidence['evidence_id']])
        self.assertEqual(len(view['results']), 1)
        self.assertEqual(view['evidence'][0]['values']['records'][0]['20260630'], 0)
        self.assertEqual(view['decisions'][0]['condition_result'], 'unknown')
        self.assertEqual(view['notifications'], [])

    def test_evidence_storage_failure_never_completes_or_creates_baseline(self):
        with self.repo.connection(True) as db:
            db.execute("CREATE TRIGGER reject_evidence BEFORE INSERT ON evidence BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        with self.assertRaises(Exception):
            self.save(self.document())
        self.core.tick()
        view = self.core.get('alice', self.mandate['mandate']['mandate_id'])
        self.assertIsNone(view['baseline'])
        self.assertEqual(view['evidence'], [])
        self.assertEqual(view['executions'][0]['status'], 'running')

    def test_source_admission_uses_same_evidence_semantics(self):
        document = copy.deepcopy(self.document())
        document['values']['period'] = '20260331'
        with self.assertRaises((Conflict, Invalid)):
            self.core.sources.accept('alice', document)
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM source_versions').fetchone()[0], 0)

    def test_discovery_cannot_report_success_for_a_different_requested_scope(self):
        other = SCOPE | {'period': '20260331'}
        document = collect(other, lambda _: {'code': '600519', 'records': [
            {'指标': '营业总收入', '20260331': 123}]})
        result = self.core.sources.discover(lambda _: document)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM source_versions').fetchone()[0], 0)

    def test_invalid_previously_saved_evidence_is_rechecked_before_result(self):
        from huohuo.contracts import canonical
        evidence = self.save(self.document())
        with self.repo.connection(True) as db:
            document = self.document()
            document['values']['period'] = '20260331'
            db.execute('UPDATE evidence SET document=? WHERE id=?', (canonical(document), evidence['evidence_id']))
        with self.assertRaises((Conflict, Invalid)):
            self.finish(self.result(evidence))
