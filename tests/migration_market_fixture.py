"""仅组合 UAT 使用的公开资料替身；控制文件不写业务队列或业务时间。"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from huohuo.market.contracts import UNITS, envelope

ROWS = [{'code': '600519', 'name': '贵州茅台'}, {'code': '600001', 'name': '核心甲'}]


class MigrationMarket:
    def __init__(self, control_file):
        self.control_file = Path(control_file)
        stamp = datetime.now(timezone.utc).isoformat()
        self.news_default = {'id':'uat-event-' + stamp, 'published_at':stamp}

    def query(self, request):
        now = datetime.now(timezone.utc).isoformat()
        control = json.loads(self.control_file.read_text()) if self.control_file.exists() else {'price': 90}
        if request['operation'] == 'news':
            news = control.get('news', self.news_default)
            return envelope('明确合成新闻', {'items': [{'id': news['id'], 'title': '合成材料需求变化',
                'content': '仅验证事件进入策略候选，不代表真实披露', 'published_at': news['published_at'],
                'source': '明确合成来源', 'url': 'https://example.invalid/uat'}]}, as_of=news['published_at'])
        price = control.get('price')
        if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
            raise ValueError('合成行情控制文件价格无效')
        return envelope('明确合成报价', {'items': [{'code': code,
            'name': next((x['name'] for x in ROWS if x['code'] == code), '合成证券'),
            'price': price, 'previous_close': 100, 'pct_change': price - 100, 'volume_ratio': 1.3,
            'turnover': 2, 'amount_yi': 3, 'volume': 100000, 'units': dict(UNITS),
            'as_of': now, 'time_known': True} for code in request.get('codes', ['600519'])]}, as_of=now)
