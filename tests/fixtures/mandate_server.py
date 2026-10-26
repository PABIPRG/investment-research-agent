"""只供隔离 UAT：真实 API/SQLite，明确合成 provider，不读取旧实例。"""
import json,sys,threading
from pathlib import Path
from huohuo.server import Service
from huohuo.research import snapshot
config=json.loads(Path(sys.argv[1]).read_text())
def fixture(scope):
 return snapshot(scope,lambda _:({'rc':0,'data':{'diff':[{'f12':scope['entity_id'].split(':')[-1],'f14':'明确合成验收数据','f2':12.1,'f18':10,'f124':1792700000}]}},'https://example.invalid/mandate-uat'))
with Service(config,researcher=fixture) as server:
 server.mandates.entities.directory=lambda:{'status':'ok','rows':[{'code':'002518','name':'科士达'},{'code':'600519','name':'贵州茅台'}],'source':{'provider':'明确合成目录'}}
 def lifetime():
  sys.stdin.buffer.read();server.shutdown()
 threading.Thread(target=lifetime,daemon=True).start()
 print('ready',flush=True);server.serve_forever(poll_interval=.1)
