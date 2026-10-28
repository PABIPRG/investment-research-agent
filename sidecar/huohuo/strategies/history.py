"""复用研究工具的有界行情来源；只取已完成的日线，不读取旧实例。"""
import math
from datetime import date, datetime, timezone
from ..research_entities.toolbox.context import ToolContext, ToolUnavailable, records_from_frame
from ..research_entities.adapters.storage_memory import InMemoryEntityRepository
from ..execution import digest

class History:
    def __init__(self):self.ctx=ToolContext(InMemoryEntityRepository(),timeout=12)
    def __call__(self,code,start,end):
        symbol=('sh' if code.startswith(('6','9')) else 'sz')+code
        try:
            frame=self.ctx.call_akshare('stock_zh_a_daily',symbol=symbol,start_date=start.replace('-',''),end_date=end.replace('-',''),adjust='qfq')
            source='akshare.stock_zh_a_daily'
        except ToolUnavailable:
            frame=self.ctx.call_akshare('stock_zh_a_hist',symbol=code,period='daily',start_date=start.replace('-',''),end_date=end.replace('-',''),adjust='qfq')
            source='akshare.stock_zh_a_hist'
        return {'records':records_from_frame(frame,limit=1100,latest_first=False),'source':source,'adjustment':'qfq'}
    def index(self,start,end):
        frame=self.ctx.call_akshare('index_zh_a_hist',symbol='000300',period='daily',start_date=start.replace('-',''),end_date=end.replace('-',''))
        return {'records':records_from_frame(frame,limit=1100,latest_first=False),'source':'akshare.index_zh_a_hist','adjustment':'none'}

def collect(provider,code,start,end,clock):
    response=provider(code,start,end)
    if not isinstance(response,dict) or not isinstance(response.get('records'),list):raise ToolUnavailable('历史行情返回格式无效')
    rows=response['records']
    if not rows:raise ToolUnavailable('所选期间没有可用的日线行情，请调整日期；本次未生成结果')
    if len(rows)>1100:raise ToolUnavailable('日线超过 1100 根，请缩短回测期间；本次未生成结果')
    aliases={'date':'日期','open':'开盘','high':'最高','low':'最低','close':'收盘','volume':'成交量'}
    clean={}
    for row in rows:
        try:
            day=str(row.get('date',row.get('日期')))[:10];date.fromisoformat(day)
            if not start<=day<=end:continue
            bar={'date':day}
            for key,alias in aliases.items():
                if key=='date':continue
                raw=row.get(key,row.get(alias))
                if type(raw) is bool:raise ValueError()
                bar[key]=float(raw)
                if not math.isfinite(bar[key]) or bar[key]<(0 if key=='volume' else 1e-12):raise ValueError()
            if bar['high']<max(bar['open'],bar['close'],bar['low']) or bar['low']>min(bar['open'],bar['close']):raise ValueError()
            if day in clean and clean[day]!=bar:raise ValueError()
            clean[day]=bar
        except (ValueError,TypeError,AttributeError):raise ToolUnavailable('历史行情存在缺失、重复冲突或非法 OHLCV，未计算收益') from None
    if not clean:raise ToolUnavailable('请求期间没有有效日线')
    records=[clean[d] for d in sorted(clean)]
    evidence={'code':code,'source':str(response.get('source') or 'unknown')[:100],
        'adjustment':response.get('adjustment'),'fetched_at':datetime.fromtimestamp(clock(),timezone.utc).isoformat(),
        'requested_window':[start,end],'actual_window':[records[0]['date'],records[-1]['date']],
        'bars':len(records),'sha256':digest(records),'records':records}
    return records,evidence
