"""同库投资事实、资料版本、联系决定与应用内投递的集成回归。"""
import unittest
import test_followup as fixtures

class IntegratedPartnerTests(unittest.TestCase):
    setUp = fixtures.FollowupTests.setUp
    tearDown = fixtures.FollowupTests.tearDown
    create = fixtures.FollowupTests.create
    document = fixtures.FollowupTests.document
    result = fixtures.FollowupTests.result
    enable = fixtures.FollowupTests.enable

    def test_execution_exposes_mandate_revision_not_execution_counter(self):
        item = self.create()
        mid = item['mandate']['mandate_id']
        self.core.tick()
        job = self.repo.claim('revision-test')
        self.assertIsNotNone(job)
        view = self.core.get('alice', mid)
        execution = next(e for e in view['executions'] if e['execution_id'] == job['execution_id'])
        self.assertEqual(execution['mandate_revision'], item['mandate']['current_revision'])
        self.assertGreater(execution['revision'], execution['mandate_revision'])

    def holding(self, quantity):
        inv=self.core.investment
        p=inv.preview('alice',{'command':'holding','payload':{'ticker':'600519','name':'贵州茅台','quantity':quantity,'cost_price':1500,'effective_at':'2026-01-01T00:00:00Z','reason':'合成集成验收'}})
        return inv.commit('alice',{'preview_id':p['preview_id'],'request_key':'holding-'+str(quantity)})

    def bind(self,mid):
        v=self.core.get('alice',mid)
        return self.core.investment_binding.bind('alice',{'mandate_id':mid,'collection':'holdings','mode':'dynamic','expected_revision':v['mandate']['current_revision'],'expected_generation':v['generation'],'expected_fact_version':self.core.investment.read('alice')['version'],'request_key':'bind-integrated'})

    def test_investment_change_reaches_review_and_delivery_without_duplicate(self):
        self.scope=fixtures.QUOTE_SCOPE
        self.enable();self.holding(100);m=self.create();mid=m['mandate']['mandate_id'];self.core.tick();self.result('unmet');self.bind(mid);self.core.tick()
        self.holding(200);self.core.tick()
        db=self.core.store._connect()
        event_job=db.execute("SELECT j.job_id,x.execution_id,x.fact_version FROM research_jobs j JOIN execution_jobs x USING(job_id) JOIN domain_events e ON e.event_id=j.trigger_event_id WHERE j.action='event_review' AND e.hook_type='investment.facts_revised' ORDER BY j.created_at DESC LIMIT 1").fetchone()
        self.assertIsNotNone(event_job)
        self.assertEqual(event_job['fact_version'],'2')
        facts=db.execute('SELECT members FROM investment_run_facts WHERE execution_id=?',(event_job['execution_id'],)).fetchone()
        self.assertIn('600519',facts[0])
        self.result('met')
        self.assertTrue(any(x['status']=='delivered' for x in self.core.notifications.list('alice')['items']))
        count=db.execute('SELECT count(*) FROM research_jobs').fetchone()[0]
        db.execute('UPDATE investment_outbox SET published=0');self.core.tick()
        self.assertEqual(db.execute('SELECT count(*) FROM research_jobs').fetchone()[0],count)

    def test_revising_contact_keeps_both_investment_and_source_dependencies(self):
        self.holding(100);m=self.create();mid=m['mandate']['mandate_id'];v=self.bind(mid)
        v=self.core.command('alice',mid,'revise',{'request_key':'revise-integrated','expected_revision':v['mandate']['current_revision'],'expected_generation':v['generation'],'goal':v['revision']['goal'],'scope':v['revision']['scope'],'contact_note':'更正联系说明'})
        self.assertIn('investment_collection',v['revision']['basis'])
        hooks=[t['hook_type'] for t in v['revision']['triggers']]
        self.assertIn('investment.facts_revised',hooks)
        self.assertGreaterEqual(len(hooks),2)
        self.assertEqual(v['investment_collection']['mode'],'dynamic')

    def test_each_independent_schema_upgrades_without_renaming_applied_migrations(self):
        import tempfile,shutil
        from pathlib import Path
        from unittest.mock import patch
        from huohuo.research_partner.adapters import sqlite_store as module
        for excluded in [('008_investment',),('008_followup_notifications',),('008_investment','008_followup_notifications')]:
            with self.subTest(excluded=excluded),tempfile.TemporaryDirectory() as tmp:
                directory=Path(tmp)/'migrations';directory.mkdir()
                for path in module._MIGRATIONS_DIR.glob('*.sql'):
                    if path.stem not in excluded and path.stem<'009':shutil.copy2(path,directory/path.name)
                dbpath=Path(tmp)/'business.sqlite'
                with patch.object(module,'_MIGRATIONS_DIR',directory):
                    old=module.SqliteBusinessStore(dbpath)
                    old._connect().execute('CREATE TABLE preserve_test(value TEXT)')
                    old._connect().execute("INSERT INTO preserve_test VALUES('keep-existing-instance')")
                    before={x[0] for x in old._connect().execute('SELECT version FROM schema_migrations')};old.close()
                upgraded=module.SqliteBusinessStore(dbpath)
                after={x[0] for x in upgraded._connect().execute('SELECT version FROM schema_migrations')}
                self.assertEqual(after-before,set(excluded)|{'009_notification_channels','010_strategies','011_strategy_run_subjects','012_strategy_schedule','014_industry_chain','015_source_heads','016_legacy_transfer','017_unified_strategy_work','018_personalization','019_position_risk','020_notification_tests','021_notification_priority','022_research_job_priority'})
                self.assertEqual(upgraded._connect().execute('SELECT value FROM preserve_test').fetchone()[0],'keep-existing-instance')
                self.assertTrue(list(Path(tmp).glob('*.before-*')))
                upgraded.close()
