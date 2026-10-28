"""隔离策略 UI 验收：真实业务 API/SQLite，显式合成行情；不连接真实模型。"""
import json,math,sys,threading
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from huohuo.server import Service
from huohuo.research_entities.security_search import search
from huohuo.strategies.service import Strategies
import huohuo.server as api

config=json.loads(Path(sys.argv[1]).read_text())
api.search_securities=lambda query:search(query,loader=lambda:[{'code':'600519','name':'贵州茅台'},{'code':'000001','name':'平安银行'}])
clock_file=Path(config['database']).parent/'strategy-ui-clock.json'
clock=[json.loads(clock_file.read_text()) if clock_file.exists() else datetime(2025,10,1,18,tzinfo=timezone.utc).timestamp()]
def history(code,start,end):
    rows=[]
    origin=date(2025,1,1)
    for i in range(600):
        day=(origin+timedelta(days=i)).isoformat()
        if not start<=day<=end:continue
        price=20+4*math.sin(i/7) if i<260 else 20+(i-260)*2
        rows.append({'date':day,'open':price,'close':price+.2,'high':price+1,'low':price-1,'volume':100000+i})
    return {'records':rows,'source':'synthetic:strategy-ui-uat','adjustment':'qfq'}
with Service(config) as service:
    strategies=Strategies(service.mandates.store,history=history,clock=lambda:clock[0])
    service.strategies=strategies;service.research_tools.strategies=strategies
    seen={r[0] for r in service.mandates.store._connect().execute("SELECT id FROM strategy_runs")}
    commit=strategies.commit
    def controlled_commit(principal,session,body):
        result=commit(principal,session,body)
        if result['run']['id'] not in seen and result['run']['action']=='shadow' and result['run']['status']=='completed':
            clock[0]+=86400
            clock_file.write_text(json.dumps(clock[0]))
        seen.add(result['run']['id'])
        return result
    strategies.commit=controlled_commit
    def stop():sys.stdin.buffer.read();service.shutdown()
    threading.Thread(target=stop,daemon=True).start()
    print('ready: synthetic strategy UI fixture',flush=True)
    service.serve_forever(poll_interval=.1)
