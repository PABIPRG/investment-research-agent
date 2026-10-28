"""最新 main 组合回归：合成数据，禁止真实网络与通知。"""
import copy
import json
import sqlite3
import unittest
from types import SimpleNamespace
import pandas as pd
import test_followup as fixtures
from test_coverage_tools import call
from huohuo.contracts import Invalid
from huohuo.research import snapshot
from huohuo.research_entities.errors import SourceUnavailable
from huohuo.research_entities.toolbox.handlers import coverage, market, valuation
from huohuo.research_entities.tool_contracts import catalog
from huohuo.research_partner.market_sources import bound_metrics
from huohuo.research_partner.source_adapters import validate_quote_document


class BaseIntegrationTests(unittest.TestCase):
    setUp=fixtures.FollowupTests.setUp
    tearDown=fixtures.FollowupTests.tearDown
    create=fixtures.FollowupTests.create
    document=fixtures.FollowupTests.document

    def test_legacy_condition_receipt_and_explicit_rule_are_one_owner(self):
        self.scope=fixtures.QUOTE_SCOPE
        condition={'type':'numeric','metric':'change_percent','operator':'>=','threshold':3}
        first=self.create(contact_condition=condition)
        request={'session_id':'test','confirmation_id':first['revision']['basis']['entity_confirmation']['confirmation_id'],
                 'request_key':'create-first','goal':first['revision']['goal'],'scope':self.scope,
                 'contact_note':'仅应用内','contact_condition':condition}
        self.assertEqual(self.core.create('alice',request)['mandate']['mandate_id'],first['mandate']['mandate_id'])
        self.assertIn('涨跌幅',first['contact_rule_description'])
        with self.assertRaises(Invalid):
            self.create(key='ambiguous',contact_condition=condition,contact_rule={'mode':'due_reminder','time':'09:00'})

    def test_quote_same_values_new_timestamp_and_return_to_prior_price(self):
        self.scope=fixtures.QUOTE_SCOPE
        a=self.document(100)
        first=self.core.sources.accept('alice',a)
        newer=copy.deepcopy(a)
        raw=newer['raw'];raw['data']['diff'][0]['f124']+=60
        newer=snapshot(self.scope,lambda _: (raw,'https://example.invalid/quote'))
        self.assertEqual(self.core.sources.accept('alice',newer),first)
        self.core.sources.accept('alice',self.document(101))
        self.assertNotEqual(self.core.sources.accept('alice',a),first)

    def test_quote_metrics_are_attempt_bound_and_cannot_be_model_numbers(self):
        self.scope=fixtures.QUOTE_SCOPE
        doc=self.document(100)
        forged=copy.deepcopy(doc);forged['values']['price']='999'
        with self.assertRaises(Invalid):validate_quote_document(forged,self.scope)
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE evidence(id TEXT,attempt_id TEXT,document TEXT)')
            db.execute('INSERT INTO evidence VALUES(?,?,?)',('ref','attempt',json.dumps(doc)))
            result={'evidence_ids':['ref'],'metrics':{'price':{'value':999}}}
            self.assertEqual(bound_metrics(db,'attempt',result,self.scope)['price']['value'],100)
            self.assertEqual(bound_metrics(db,'other',result,self.scope),{})

    def test_quote_holiday_and_unknown_calendar_do_not_collect(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.scope=fixtures.QUOTE_SCOPE
        self.repo.clock=lambda:datetime(2026,10,26,10,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        self.create()
        def forbidden(_):raise AssertionError('不得在假日或日历未知时采集')
        self.core.service.calendar=SimpleNamespace(is_trading_day=lambda _:False)
        self.assertFalse(self.core.sources.discover(forbidden)['checked'])
        self.core.service.calendar=None
        self.assertFalse(self.core.sources.discover(forbidden)['checked'])
        row=self.core.store._connect().execute('SELECT status FROM source_checks').fetchone()
        self.assertEqual(row[0],'unavailable')

    def test_legacy_null_resets_condition_and_can_cancel_old_reminder(self):
        self.scope=fixtures.QUOTE_SCOPE
        first=self.create(contact_condition={'type':'numeric','metric':'price','operator':'>','threshold':100})
        mid=first['mandate']['mandate_id']
        body={'request_key':'legacy-reset','expected_revision':1,'expected_generation':0,
              'goal':first['revision']['goal'],'scope':self.scope,'contact_note':'重置默认规则',
              'reminder_time':None,'contact_condition':None}
        result=self.core.command('alice',mid,'revise',body)
        self.assertEqual(result['revision']['contact_policy']['condition']['claim'],'notable_change')
        self.assertEqual(self.core.command('alice',mid,'revise',body)['revision'],result['revision'])

    def test_old_scope_without_subscription_is_not_shown_as_tracking(self):
        self.scope=fixtures.QUOTE_SCOPE
        first=self.create();mid=first['mandate']['mandate_id']
        db=self.core.store._connect()
        db.execute("UPDATE mandate_revisions SET triggers_json='[]' WHERE mandate_id=?",(mid,))
        view=self.core.get('alice',mid)
        self.assertFalse(view['monitoring']['enabled'])
        self.assertIn('重新确认',view['monitoring']['detail'])

    def test_legacy_semantic_unmet_uses_evidence_and_readable_description(self):
        self.scope=fixtures.PROFILE_SCOPE
        view=self.create(contact_condition={'claim':'已获得订单','expected':'unmet'})
        self.assertIn('证伪',view['contact_rule_description'])
        self.core.tick()
        def complete(document):
            job=self.repo.claim('fixture-worker');self.assertIsNotNone(job)
            evidence=self.repo.save_evidence(job['attempt_id'],job['lease_token'],document)
            self.repo.finish(job['attempt_id'],job['lease_token'],{'status':'succeeded',
                'execution_id':job['execution_id'],'scope':self.scope,'summary':'合成资料核对',
                'evidence_ids':[evidence['evidence_id']],
                'judgements':{'已获得订单':{'judgement':'unmet','reason':'合成资料明确证伪',
                    'evidence_refs':[evidence['evidence_id']]}}})
            self.core.tick()
        complete(self.document())
        changed=fixtures.collect(self.scope,lambda _: {'code':'600519','records':[{'公司名称':'贵州茅台','主营业务':'合成资料修改'}]})
        self.core.sources.accept('alice',changed);self.core.tick();complete(changed)
        decisions=self.core.get('alice',view['mandate']['mandate_id'])['decisions']
        self.assertTrue(any(d['condition_result']=='met' for d in decisions))

    def test_object_tools_do_not_accept_arbitrary_code(self):
        specs={s['name']:s['parameters'] for s in catalog()}
        for name in ('research_report_lookup','announcement_document_lookup','ipo_detail_lookup'):
            self.assertIn('confirmation_id',specs[name]['required'])
            self.assertNotIn('code',specs[name]['properties'])

    def test_source_failures_are_not_empty_or_sensitive_diagnostics(self):
        secret='fixture-only-proxy-user:fixture-only-password@example.invalid /private/fixture-home'
        error=SourceUnavailable(secret)
        news=market.market_news_lookup(call('market_news_lookup',frames={
            'stock_info_global_em':error,'stock_info_global_cls':error}))
        self.assertEqual(news.status,'unavailable')
        results=[news,coverage.forex_rate_lookup(call('forex_rate_lookup',frames={'forex_spot_em':error}))]
        for result in results:self.assertNotIn(secret,result.model_dump_json())
        with self.assertRaises(SourceUnavailable):
            market._breadth_from_spot(call('market_overview_lookup',frames={'stock_zh_a_spot_em':pd.DataFrame()}))
