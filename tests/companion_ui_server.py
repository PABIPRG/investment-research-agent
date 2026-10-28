"""仅本机合成动效验收：让真实工具派发阶段可观察，不访问真实来源。"""
import runpy
import time
from pathlib import Path
from migration_market_fixture import MigrationMarket

query = MigrationMarket.query


def delayed(self, request):
    time.sleep(10)
    return query(self, request)


MigrationMarket.query = delayed
runpy.run_path(str(Path(__file__).with_name('migration_ui_server.py')), run_name='__main__')
