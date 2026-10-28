"""Baostock 公共第三回退：固定查询、进程截止、单位/未知与行数上限。"""
import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from huohuo.market.baostock_daily import DEADLINE, FIELDS, fetch_daily, read_sdk
from huohuo.market.contracts import CN


class Result:
    error_code = '0'

    def __init__(self, rows):
        self.rows = iter(rows)
        self.current = None

    def next(self):
        self.current = next(self.rows, None)
        return self.current is not None

    def get_row_data(self):
        return self.current


def sdk(rows):
    return SimpleNamespace(login=Mock(return_value=SimpleNamespace(error_code='0')),
                           logout=Mock(), query_history_k_data_plus=Mock(return_value=Result(rows)))


def row(**changes):
    values = dict(zip(FIELDS, [datetime.now(CN).date().isoformat(), '10', '11', '9', '10', '1000', '10000']))
    return [changes.get(key, values[key]) for key in FIELDS]


class BaostockTests(unittest.TestCase):
    def test_anonymous_readonly_qfq_query_and_units(self):
        client = sdk([row()])
        result = read_sdk(client, '600519', 20)
        client.login.assert_called_once_with(user_id='anonymous', password='123456')
        args, kwargs = client.query_history_k_data_plus.call_args
        self.assertEqual(args, ('sh.600519', 'date,open,high,low,close,volume,amount'))
        self.assertEqual(kwargs['frequency'], 'd')
        self.assertEqual(kwargs['adjustflag'], '2')
        self.assertEqual(result[0]['volume'], 1000)
        self.assertEqual(result[0]['amount'], 10000)
        client.logout.assert_called_once_with()

    def test_nonfinite_unknown_and_invalid_dates(self):
        client = sdk([row(volume='NaN', amount='inf')])
        result = read_sdk(client, '000001', 20)
        self.assertIsNone(result[0]['volume'])
        self.assertIsNone(result[0]['amount'])
        for date in ('1999-01-01', (datetime.now(CN).date() + timedelta(days=1)).isoformat()):
            client = sdk([row(date=date)])
            with self.assertRaises(ValueError):
                read_sdk(client, '000001', 20)
            client.logout.assert_called_once_with()

    def test_row_limit_login_failure_and_pagination_failure(self):
        client = sdk([row()] * 523)
        with self.assertRaises(ValueError):
            read_sdk(client, '600519', 250)
        client.logout.assert_called_once_with()
        client = sdk([])
        client.login.return_value.error_code = '1'
        with self.assertRaises(ValueError):
            read_sdk(client, '600519', 20)
        client.logout.assert_not_called()
        client = sdk([])
        client.query_history_k_data_plus.return_value.error_code = '1'
        with self.assertRaises(ValueError):
            read_sdk(client, '600519', 20)
        client.logout.assert_called_once_with()

    def test_subprocess_timeout_is_bounded_not_empty_success(self):
        with patch('huohuo.market.baostock_daily.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', DEADLINE + 1)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                fetch_daily('600519', 20)
        self.assertEqual(run.call_args.kwargs['timeout'], 7)
        with patch('huohuo.market.baostock_daily.subprocess.run', return_value=SimpleNamespace(returncode=124, stdout='')):
            with self.assertRaises(ValueError):
                fetch_daily('600519', 20)

    def test_isolated_worker_watchdog_exits_hanging_sdk(self):
        # 实际启动隔离进程；SDK 注入为卡住的纯本地替身，不访问任何网络。
        script = """
import io,sys,time,types
from huohuo.market import baostock_daily as b
b.DEADLINE=.1
b.read_sdk=lambda *args: time.sleep(10)
sys.stdin=io.StringIO('{"code":"600519","lookback":20}')
for name in ['baostock','baostock.common','baostock.common.context','baostock.common.contants']:
 sys.modules[name]=types.ModuleType(name)
sys.modules['baostock.common.contants'].BAOSTOCK_SERVER_IP=b.HOST
sys.modules['baostock.common.contants'].BAOSTOCK_SERVER_PORT=b.PORT
b.worker()
"""
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 124, result.stderr)


if __name__ == '__main__':
    unittest.main()
