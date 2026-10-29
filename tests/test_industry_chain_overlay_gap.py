import tempfile
import unittest
from pathlib import Path
from huohuo.industry_chain import IndustryChainService
from huohuo.research_entities.toolbox.context import ToolUnavailable
from test_industry_chain_fixtures import Fixture, overlay


class OverlayGapTest(unittest.TestCase):
    def test_company_outside_seed_is_queryable_after_confirmed_overlay(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(directory)
            f.install(); f.evidence(code='600009')
            value = overlay()
            value['companies'][0]['code'] = '600009'
            self.assertEqual(f.commit(f.preview('overlay', value))['status'], 'committed')
            profile = f.service.query('p', '/companies/600009')
            self.assertEqual(profile['supplier_count'], 1)
            self.assertIsNone(profile['name'])
            self.assertFalse(profile['is_subject'])
            self.assertEqual(profile['sources'][0]['evidence_id'], 'ev1')
            chain = f.service.query('p', '/graph/chain/600009')
            self.assertEqual(chain['up_levels'][0]['nodes'][0]['name'], '新供应商')
            self.assertEqual(f.service.query('p', '/companies', {'keyword': '600009'})['items'][0]['code'], '600009')
            restarted = IndustryChainService(Path(directory)/'chain', f.repo, http_get=f.source)
            self.assertEqual(restarted.query('p', '/companies/600009')['supplier_count'], 1)
            with self.assertRaises(ToolUnavailable): restarted.query('other', '/companies/600009')
            self.assertIsNone(restarted.graph._load('view-data-all.json')['companies'].get('600009'))

    def test_incremental_company_keeps_non_subject_status_in_entity_view(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(directory); f.install(); f.evidence(code='600009')
            value = overlay(); value['companies'][0]['code'] = '600009'
            f.commit(f.preview('overlay', value))
            self.assertFalse(f.service.query('p', '/graph/entity/600009')['is_subject'])
