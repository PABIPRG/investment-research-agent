"""没有成功基准的事件必须等待；恢复后不能丢失已保存的来源。"""
import unittest
from test_followup import FollowupTests


class BaselineGateTests(unittest.TestCase):
    setUp = FollowupTests.setUp
    tearDown = FollowupTests.tearDown
    create = FollowupTests.create
    document = FollowupTests.document
    result = FollowupTests.result
    jobs = FollowupTests.jobs

    def test_failed_baseline_keeps_source_event_waiting_across_restart(self):
        self.create()
        self.core.tick()
        self.core.sources.accept('alice', self.document())
        self.result(fail=True)
        self.core.store.close()
        self.core = type(self.core)(self.repo, 'test')
        self.core.tick()
        self.assertIsNone(self.repo.claim('worker'))
        event_jobs = [j for j in self.jobs() if j['action'] == 'event_review']
        self.assertEqual([j['status'] for j in event_jobs], ['pending'])

    def test_resume_rebuilds_baseline_then_releases_saved_event_once(self):
        mid = self.create()['mandate']['mandate_id']
        self.core.tick()
        self.core.sources.accept('alice', self.document())
        self.result(fail=True)
        self.core.command('alice', mid, 'pause', {
            'request_key': 'pause-test', 'expected_revision': 1, 'expected_generation': 0})
        self.core.command('alice', mid, 'resume', {
            'request_key': 'resume-test', 'expected_revision': 1, 'expected_generation': 1})
        self.core.tick()
        self.result()
        self.core.tick()
        job = self.repo.claim('worker')
        self.assertIsNotNone(job)
        self.assertIn('event_review', job['question'])
        self.assertIsNone(self.repo.claim('worker'))

    def test_explicit_baseline_retry_is_idempotent_and_keeps_scope(self):
        mid = self.create()['mandate']['mandate_id']
        self.core.tick()
        self.result(fail=True)
        body = {'request_key': 'retry-baseline', 'expected_revision': 1, 'expected_generation': 0}
        first = self.core.command('alice', mid, 'retry_baseline', body)
        self.assertEqual(first, self.core.command('alice', mid, 'retry_baseline', body))
        self.core.tick()
        self.result()
        self.assertIsNotNone(self.core.get('alice', mid)['baseline'])


if __name__ == '__main__':
    unittest.main()
