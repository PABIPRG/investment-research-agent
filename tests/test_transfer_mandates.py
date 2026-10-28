"""旧委托正式导入后的可读性、重新确认与恢复门禁。"""
import tempfile
import unittest
from datetime import datetime, timezone
from huohuo.contracts import Invalid
from huohuo.execution import Conflict
from test_transfer_fixtures import Fixture, mandate_entry, package


class TransferMandateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.f = Fixture(self.tmp.name); self.addCleanup(self.f.store.close)

    def imported(self):
        self.f.commit(self.f.preview(self.f.upload(package(mandates=[mandate_entry()]))))
        return self.f.core.list('owner')['items'][0]

    def command(self, view, action, **values):
        return self.f.core.command('owner', view['mandate']['mandate_id'], action, {
            'request_key': 'import-' + action + str(view['generation']),
            'expected_revision': view['mandate']['current_revision'],
            'expected_generation': view['generation'], **values})

    def definition(self, view):
        return {'goal': view['revision']['goal'], 'scope': view['revision']['scope'],
                'contact_note': '重新核对后仅在应用内查看',
                'contact_rule': {'mode': 'condition', 'condition': {'type': 'semantic', 'claim': 'notable_change'}},
                'contact_channels': ['app']}

    def test_incompatible_scope_blocks_before_formal_commit(self):
        for scope in ({}, {'entity_id': 'old-company'}, {'entity_id': 'SEC:CN:A:600519', 'exchange': 'SSE', 'operation': 'unknown'}):
            entry = mandate_entry(); entry['revisions'][0]['revision']['scope'] = scope
            preview = self.f.preview(self.f.upload(package(mandates=[entry])))
            self.assertFalse(preview['can_commit'])
            self.assertEqual(preview['blockers'][0]['category'], 'mandates')
            with self.assertRaises(Invalid): self.f.commit(preview)
            self.assertEqual(self.f.core.list('owner')['items'], [])

    def test_imported_mandate_requires_review_even_if_requirement_is_waived(self):
        view = self.imported()
        for item in view['requirements']:
            self.f.store.update_requirement(item['requirement_id'], status='waived', resolved_at=datetime.now(timezone.utc))
        with self.assertRaises((Invalid, Conflict)):
            self.command(view, 'resume')
        self.assertEqual(self.f.core.get('owner', view['mandate']['mandate_id'])['mandate']['status'], 'paused')

    def test_review_requires_explicit_rule_and_channels(self):
        view = self.imported()
        for key in ('contact_rule', 'contact_channels'):
            definition = self.definition(view); definition.pop(key)
            with self.assertRaises(Invalid): self.command(view, 'revise', **definition)
        self.assertEqual(self.f.core.get('owner', view['mandate']['mandate_id'])['mandate']['current_revision'], 1)

    def test_review_then_resume_is_consistent_and_preserves_old_revision(self):
        view = self.imported(); mid = view['mandate']['mandate_id']
        revised = self.command(view, 'revise', **self.definition(view))
        self.assertEqual(revised['mandate']['status'], 'paused')
        self.assertFalse(revised['revision']['basis']['legacy_import']['requires_review'])
        self.assertEqual(revised['revision']['contact_policy']['channels'], ['app'])
        self.assertFalse(any(x['status'] == 'open' for x in revised['requirements']))
        self.assertTrue(self.f.store.get_revision(mid, 1).basis['legacy_import']['requires_review'])
        resumed = self.command(revised, 'resume')
        self.assertEqual(resumed['mandate']['status'], 'tracking')
        self.f.core.tick()
        self.assertEqual(len(self.f.core.get('owner', mid)['executions']), 1)

    def test_failed_review_rolls_back_requirement_resolution(self):
        view = self.imported(); definition = self.definition(view)
        definition['contact_channels'] = ['unconfigured-external']
        with self.assertRaises(Invalid): self.command(view, 'revise', **definition)
        current = self.f.core.get('owner', view['mandate']['mandate_id'])
        self.assertTrue(current['revision']['basis']['legacy_import']['requires_review'])
        self.assertTrue(any(x['code'] == 'legacy_import_review' and x['status'] == 'open' for x in current['requirements']))
