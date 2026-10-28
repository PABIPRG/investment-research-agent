"""Baostock 第三日线回退：只读匿名公共 TCP；不接受凭据或端点。"""
import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import threading
from datetime import datetime, timedelta

from .contracts import CN, bounded_int, number, security_code

DEADLINE = 6
FIELDS = ('date', 'open', 'high', 'low', 'close', 'volume', 'amount')
HOST, PORT = 'public-api.baostock.com', 10030


def read_sdk(sdk, code, lookback):
    """由隔离子进程调用；公开 SDK 日线价格元/股、成交量股、成交额元。"""
    code = security_code(code)
    lookback = bounded_int(lookback, 20, 250, 'lookback')
    end = datetime.now(CN).date()
    start = end - timedelta(days=lookback * 2 + 20)
    logged_in = False
    try:
        login = sdk.login(user_id='anonymous', password='123456')
        if login.error_code != '0':
            raise ValueError('Baostock public anonymous login unavailable')
        logged_in = True
        result = sdk.query_history_k_data_plus(
            ('sh.' if code.startswith('6') else 'sz.') + code, ','.join(FIELDS),
            start_date=start.isoformat(), end_date=end.isoformat(), frequency='d', adjustflag='2')
        if result.error_code != '0':
            raise ValueError('Baostock daily query unavailable')
        rows = []
        # 日历窗口最多 521 天；防止提供方错误地无限翻页。
        for _ in range(522):
            if not result.next():
                break
            values = result.get_row_data()
            if len(values) != len(FIELDS):
                raise ValueError('Baostock daily shape mismatch')
            row = dict(zip(FIELDS, values))
            day = datetime.strptime(row['date'], '%Y-%m-%d').date()
            if not start <= day <= end:
                raise ValueError('Baostock daily date outside requested window')
            rows.append({'date': day.isoformat(), **{key: number(row[key]) for key in FIELDS[1:]}})
        else:
            raise ValueError('Baostock daily row limit exceeded')
        if result.error_code != '0':
            raise ValueError('Baostock daily pagination failed')
        return rows[-lookback:]
    finally:
        if logged_in:
            sdk.logout()


def fetch_daily(code, lookback):
    request = {'code': security_code(code), 'lookback': bounded_int(lookback, 20, 250, 'lookback')}
    result = subprocess.run([sys.executable, '-m', 'huohuo.market.baostock_daily'],
                            input=json.dumps(request), capture_output=True, text=True, timeout=DEADLINE + 1)
    if result.returncode or len(result.stdout) > 200_000:
        raise ValueError('Baostock isolated daily query unavailable')
    rows = json.loads(result.stdout)
    if not isinstance(rows, list) or len(rows) > lookback:
        raise ValueError('Baostock daily response exceeds bound')
    return rows


def worker():
    # 即使外层 provider 先被终止，本进程仍有独立硬截止，不能留下无界 SDK 子进程。
    watchdog = threading.Timer(DEADLINE, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    try:
        request = json.loads(sys.stdin.read(1000))
        if set(request) != {'code', 'lookback'}:
            raise ValueError('invalid Baostock request')
        import baostock as sdk
        import baostock.common.context as context
        import baostock.common.contants as constants
        if (constants.BAOSTOCK_SERVER_IP, constants.BAOSTOCK_SERVER_PORT) != (HOST, PORT):
            raise ValueError('unexpected Baostock endpoint')
        context.apiKey = '0'  # 不读取环境、设置或 SDK 中的私有 API key。
        socket.setdefaulttimeout(2)
        with contextlib.redirect_stdout(io.StringIO()):
            rows = read_sdk(sdk, request['code'], request['lookback'])
        print(json.dumps(rows, allow_nan=False))
    finally:
        watchdog.cancel()


if __name__ == '__main__':
    worker()
