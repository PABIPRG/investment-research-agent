"""数值条件与简报联系资格不能由引用顺序或等待时长改变事实。"""
import copy
import json
import sqlite3
import unittest
from datetime import datetime
from huohuo.execution import digest
from huohuo.research_partner.market_sources import bound_metrics, collect_market
from huohuo.research_partner.market_freshness import fresh_for_contact
from test_market_integration import Market, SCOPE
from test_market_brief_basis import fixture, KnownCalendar

class MarketEvidenceBindingTests(unittest.TestCase):
    def test_latest_source_time_wins_regardless_of_model_reference_order(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE evidence(id TEXT,attempt_id TEXT,document TEXT)')
            for ref, stamp, price in [('old','2026-10-27T08:00:00+00:00',90),('new','2026-10-27T08:01:00+00:00',110)]:
                doc=collect_market(SCOPE,Market())
                doc['raw']['data']['items'][0].update(as_of=stamp,price=price)
                doc['source_hash']=digest(doc['raw'])
                db.execute('INSERT INTO evidence VALUES(?,?,?)',(ref,'attempt',json.dumps(doc)))
            for refs in (['old','new'],['new','old']):
                result=bound_metrics(db,'attempt',{'evidence_ids':refs},SCOPE)
                self.assertEqual(result['price']['value'],110)
                self.assertEqual(result['price']['evidence_refs'],['new'])
            conflicting=copy.deepcopy(doc);conflicting['raw']['data']['items'][0]['price']=80
            conflicting['source_hash']=digest(conflicting['raw'])
            db.execute('INSERT INTO evidence VALUES(?,?,?)',('conflict','attempt',json.dumps(conflicting)))
            self.assertNotIn('price',bound_metrics(db,'attempt',{'evidence_ids':['new','conflict']},SCOPE))

    def test_close_reference_does_not_make_two_hour_old_news_fresh(self):
        scope={**SCOPE,'operation':'market_brief','period':'post'}
        doc={'raw':fixture(),'observed_at':'2026-10-27T16:00:00+08:00'}
        self.assertTrue(fresh_for_contact(doc,scope,datetime.fromisoformat('2026-10-27T16:01:00+08:00').timestamp(),KnownCalendar()))
        self.assertFalse(fresh_for_contact(doc,scope,datetime.fromisoformat('2026-10-27T18:00:00+08:00').timestamp(),KnownCalendar()))
