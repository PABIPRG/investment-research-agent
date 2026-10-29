import copy
import unittest
from datetime import datetime, timezone
from huohuo.investment.valuation import account_view
from huohuo.market.contracts import validate
from huohuo.market.quotes import secid

NOW=datetime(2026,10,29,2,tzinfo=timezone.utc)
def facts(holdings=None,trades=None,corrections=None):
    return {'version':3,'holdings_status':'not_recorded' if holdings is None else 'recorded','holdings':holdings or [],
            'watchlist':[],'trades':trades or [],'corrections':corrections or []}
def position(code='000001',quantity=100,cost=10):
    return {'ticker':code,'quantity':quantity,'cost_price':cost,'position_time':'2026-10-28T08:00:00+08:00'}
def trade(side,quantity,price,fees=0):
    return {'ticker':'000001','side':side,'quantity':quantity,'price':price,'fees':fees,
            'traded_at':'2026-10-29T09:40:00+08:00','affects_holdings':True,'before_quantity':100}
class Market:
    def __init__(self,rows=None,status='ok',stale=False):self.calls=[];self.rows=rows;self.status=status;self.stale=stale
    def query(self,req):
        self.calls.append(req)
        rows=self.rows if self.rows is not None else [{'code':c,'price':12,'previous_close':11,'units':{'price':'CNY/share','previous_close':'CNY/share'},'as_of':NOW.isoformat(),'stale':self.stale,'source':'fixture'} for c in req['codes']]
        return {'status':self.status,'stale':self.stale,'complete':True,'data':{'items':rows},'source':'fixture','warnings':[]}
class AccountTests(unittest.TestCase):
    def test_empty_success_is_zero_without_quote_request(self):
        m=Market();v=account_view(facts(),m,now=NOW)
        self.assertEqual(v['holdings_count'],0);self.assertEqual(v['watchlist_count'],0)
        for key in ['market_value','holding_cost','daily_pnl']:self.assertEqual(v[key]['value'],0)
        self.assertEqual(v['holdings_status'],'not_recorded');self.assertEqual(m.calls,[])
    def test_market_value_cost_and_daily_change(self):
        m=Market();v=account_view(facts([position()]),m,now=NOW)
        self.assertEqual(v['market_value']['value'],1200);self.assertEqual(v['holding_cost']['value'],1000)
        self.assertEqual(v['daily_pnl']['value'],100);self.assertEqual(v['fact_version'],3)
    def test_quote_failure_is_not_zero_and_cost_is_independent(self):
        v=account_view(facts([position()]),Market(status='unavailable'),now=NOW)
        self.assertIsNone(v['market_value']['value']);self.assertEqual(v['market_value']['status'],'unavailable')
        self.assertEqual(v['holding_cost']['value'],1000)
    def test_missing_one_quote_does_not_publish_partial_total(self):
        row={'code':'000001','price':12,'previous_close':11,'units':{'price':'CNY/share','previous_close':'CNY/share'},'as_of':NOW.isoformat()}
        v=account_view(facts([position(),position('600519')]),Market([row]),now=NOW)
        self.assertIsNone(v['market_value']['value']);self.assertIn('600519',v['missing_codes'])
    def test_unknown_cost_does_not_prevent_market_value(self):
        v=account_view(facts([position(cost=None)]),Market(),now=NOW)
        self.assertEqual(v['market_value']['value'],1200);self.assertIsNone(v['holding_cost']['value'])
    def test_stale_quote_is_labeled_reference_and_not_current_daily_pnl(self):
        row={'code':'000001','price':12,'previous_close':11,'units':{'price':'CNY/share','previous_close':'CNY/share'},'as_of':'2026-10-28T07:00:00+00:00','stale':True}
        v=account_view(facts([position()]),Market([row],stale=True),now=NOW)
        self.assertEqual(v['market_value']['value'],1200);self.assertEqual(v['market_value']['status'],'stale')
        self.assertIsNone(v['daily_pnl']['value'])
    def test_buy_and_sell_use_actual_prices_and_fees(self):
        v=account_view(facts([position(quantity=140)],[trade('buy',50,11.5,2),dict(trade('sell',10,12,1),before_quantity=150)]),Market(),now=NOW)
        self.assertEqual(v['daily_pnl']['value'],122)
    def test_closed_position_can_have_nonzero_daily_profit(self):
        v=account_view(facts([],[dict(trade('buy',100,10,1),before_quantity=0),trade('sell',100,12,1)]),Market(),now=NOW)
        self.assertEqual(v['market_value']['value'],0);self.assertEqual(v['daily_pnl']['value'],198)
    def test_today_correction_or_record_only_trade_leaves_daily_unknown(self):
        for f in [facts([position()],corrections=[{'ticker':'000001','effective_at':NOW.isoformat(),'before':None,'after':position()}]),
                  facts([],trades=[dict(trade('buy',100,10),affects_holdings=False)])]:
            self.assertIsNone(account_view(f,Market(),now=NOW)['daily_pnl']['value'])
    def test_quote_wrong_unit_time_or_duplicate_is_unknown(self):
        row={'code':'000001','price':12,'previous_close':11,'units':{'price':'point','previous_close':'point'},'as_of':NOW.isoformat()}
        for rows in [[row],[dict(row,units={'price':'CNY/share'},as_of=None)],[row,row]]:
            self.assertIsNone(account_view(facts([position()]),Market(rows),now=NOW)['market_value']['value'])
    def test_funds_require_explicit_scope_and_correct_exchange(self):
        with self.assertRaises(Exception):validate({'operation':'quotes','codes':['513130']})
        self.assertEqual(validate({'operation':'quotes','codes':['513130','159740'],'asset_scope':'investment'})['codes'],['513130','159740'])
        self.assertEqual(secid('513130'),'1.513130');self.assertEqual(secid('159740'),'0.159740')
    def test_before_trade_quote_cannot_be_current_daily_profit(self):
        row={'code':'000001','price':12,'previous_close':11,'units':{'price':'CNY/share','previous_close':'CNY/share'},'as_of':'2026-10-29T01:31:00+00:00'}
        v=account_view(facts([position(quantity=150)],[trade('buy',50,11.5)]),Market([row]),now=NOW)
        self.assertIsNone(v['daily_pnl']['value'])
    def test_read_does_not_mutate_facts(self):
        f=facts([position()]);before=copy.deepcopy(f)
        account_view(f,Market(),now=NOW)
        self.assertEqual(f,before)
    def test_more_than_twenty_is_explicit_gap_without_partial_query(self):
        holdings=[position('600'+str(i).zfill(3)) for i in range(21)]
        m=Market();v=account_view(facts(holdings),m,now=NOW)
        self.assertEqual(m.calls,[]);self.assertIsNone(v['market_value']['value'])
        self.assertEqual(len(v['missing_codes']),21)
