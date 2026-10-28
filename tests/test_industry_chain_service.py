import tempfile
import unittest
from pathlib import Path
from huohuo.contracts import Invalid
from huohuo.execution import Conflict, Missing
from huohuo.industry_chain import IndustryChainService
from huohuo.research_entities.toolbox.context import ToolUnavailable
from test_industry_chain_fixtures import Fixture, dataset, overlay


class IndustryChainServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.f = Fixture(self.tmp.name)
        self.service = self.f.service

    def test_read_and_prepare_never_download(self):
        self.assertEqual(self.service.status('p')['state'], 'missing')
        with self.assertRaises(ToolUnavailable): self.service.query('p', '/stats')
        preview = self.f.preview()
        self.assertTrue(preview['requires_confirmation'])
        self.assertIn('许可', preview['summary'])
        self.assertEqual(self.f.source.calls, [])
        with self.assertRaises(Invalid): self.f.preview(payload={'acknowledge_source_terms': False})

    def test_confirmation_ownership_idempotence_and_bounds(self):
        preview = self.f.preview()
        with self.assertRaises(Missing): self.f.commit(preview, 'other')
        with self.assertRaises(Missing): self.f.commit(preview, session='other')
        receipt = self.f.commit(preview)
        self.assertEqual(receipt['status'], 'committed')
        self.assertEqual(receipt['data']['state'], 'ready')
        self.assertEqual(self.f.commit(preview), receipt)
        self.assertEqual(len(self.f.source.calls), 5)
        for _, kwargs in self.f.source.calls:
            self.assertFalse(kwargs['allow_redirects'])
        for params in ({'depth_up': 6}, {'top_up': 0}, {'depth_down': True}, {'depth_up': float('nan')}, {'unexpected': 1}):
            with self.assertRaises(Invalid): self.service.query('p', '/graph/chain/600001', params)
        with self.assertRaises(Invalid): self.service.query('p', 'https://example.invalid')
        with self.assertRaises(Invalid): self.service.query('p', '/companies/../../secret')

    def test_all_graph_views_preserve_source_and_zeros(self):
        self.f.install()
        self.assertEqual(self.service.query('p', '/stats')['subject_count'], 2)
        self.assertEqual(self.service.query('p', '/companies', {'keyword': '核心'})['items'][0]['name'], '核心甲')
        self.assertEqual(self.service.query('p', '/companies/600001')['supplier_count'], 1)
        graph = self.service.query('p', '/graph/chain/600001')
        supplier = graph['up_levels'][0]['nodes'][0]
        self.assertEqual((supplier['share'], supplier['share_source']), (0, 'disclosed'))
        customer = graph['down_levels'][0]['nodes'][0]
        self.assertEqual((customer['share'], customer['share_source']), (None, 'inferred'))
        self.assertEqual(self.service.query('p', '/graph/single/600001')['suppliers'][0]['share'], 0)
        self.assertFalse(self.service.query('p', '/graph/entity/600003')['is_subject'])
        network = self.service.query('p', '/graph/network', {'min_degree': 0, 'min_share': 10})
        self.assertEqual(len(network['links']), 1)
        self.assertEqual(network['links'][0]['share_source'], 'inferred')
        self.assertEqual(network['provenance']['source']['license_status'], 'not_verified')
        with self.assertRaises(ToolUnavailable): self.service.query('p', '/graph/network', {'include_universe': True})

    def test_cache_isolation_refresh_and_restarts(self):
        self.f.install()
        first = self.service.query('p', '/companies/600001')
        first['name'] = 'caller mutated'
        with tempfile.TemporaryDirectory() as directory:
            other = Fixture(directory)
            other.source.data = dataset('另一实例')
            other.install()
            self.assertEqual(other.service.query('p', '/companies/600001')['name'], '另一实例')
        self.assertEqual(self.service.query('p', '/companies/600001')['name'], '核心甲')
        self.f.source.data = dataset('刷新版本')
        self.assertEqual(self.f.commit(self.f.preview('refresh'))['status'], 'committed')
        self.assertEqual(self.service.query('p', '/companies/600001')['name'], '刷新版本')
        restarted = IndustryChainService(Path(self.tmp.name)/'chain', self.f.repo, http_get=self.f.source)
        self.assertEqual(restarted.query('p', '/companies/600001')['name'], '刷新版本')
        self.assertEqual(len(self.f.source.calls), 10)

    def test_overlay_requires_same_session_evidence_and_is_transactional(self):
        self.f.install()
        with self.assertRaises(Invalid): self.f.preview('overlay', overlay())
        self.f.evidence(session='other')
        with self.assertRaises(Invalid): self.f.preview('overlay', overlay())
        self.f.evidence()
        preview = self.f.preview('overlay', overlay())
        receipt = self.f.commit(preview)
        self.assertEqual(receipt['data']['overlay_revision'], 1)
        self.assertEqual(self.service.query('p', '/companies/600001')['supplier_count'], 2)
        self.assertEqual(self.service.query('other', '/companies/600001')['supplier_count'], 1)
        receipt = self.f.commit(self.f.preview('clear_overlay', {'codes': ['600001']}))
        self.assertEqual(receipt['status'], 'committed')
        self.assertEqual(self.service.query('p', '/companies/600001')['supplier_count'], 1)
        self.assertEqual(self.service.graph._load('view-data-all.json')['companies']['600001']['materials'][0]['name'], '材料甲')

    def test_expired_and_stale_previews_do_not_write(self):
        preview = self.f.preview()
        self.f.clock += 1801
        with self.assertRaises(Conflict): self.f.commit(preview)
        first = self.f.preview()
        second = self.f.preview()
        self.f.commit(first)
        with self.assertRaises(Conflict): self.f.commit(second)
        self.assertEqual(len(self.f.source.calls), 5)

    def test_failed_refresh_retains_old_generation(self):
        self.f.install()
        previous = self.service.status('p')['generation']
        self.f.source.failure = RuntimeError('synthetic network failure')
        receipt = self.f.commit(self.f.preview('refresh'))
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(self.service.status('p')['generation'], previous)
        self.assertTrue(self.service.status('p')['available'])
        self.assertFalse(list((Path(self.tmp.name)/'chain').glob('.staging-*')))
        self.assertEqual(self.service.query('p', '/companies/600001')['name'], '核心甲')

    def test_recovery_uses_published_operation_and_never_retries_network(self):
        preview = self.f.preview()
        with self.f.repo.connection(True) as db:
            db.execute("UPDATE industry_chain_previews SET status='running' WHERE id=?", (preview['preview_id'],))
        self.service.seed.download(preview['preview_id'])
        self.service.recovery()
        receipt = self.f.commit(preview)
        self.assertEqual(receipt['status'], 'committed')
        self.assertEqual(len(self.f.source.calls), 5)
        second = self.f.preview('refresh')
        with self.f.repo.connection(True) as db:
            db.execute("UPDATE industry_chain_previews SET status='running' WHERE id=?", (second['preview_id'],))
        self.service.recovery()
        self.assertEqual(self.f.commit(second)['status'], 'interrupted')
        self.assertEqual(len(self.f.source.calls), 5)

    def test_delete_retains_confirmed_overlay_only(self):
        self.f.install(); self.f.evidence()
        self.f.commit(self.f.preview('overlay', overlay()))
        receipt = self.f.commit(self.f.preview('delete'))
        self.assertEqual(receipt['data']['state'], 'missing')
        self.assertEqual(receipt['data']['overlay_companies'], 1)
        self.assertFalse(list((Path(self.tmp.name)/'chain').glob('seed-*')))
        with self.assertRaises(ToolUnavailable): self.service.query('p', '/stats')
