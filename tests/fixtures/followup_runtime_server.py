"""本次新建隔离实例专用：报价明确合成，财务复核必须读已绑定来源。"""
import json
import sys
import threading
from pathlib import Path
from huohuo import server as api
from huohuo.research import snapshot

config = json.loads(Path(sys.argv[1]).read_text())

def quote(scope):
    document = snapshot(scope, lambda _: ({'data': {'diff': [{
        'f12': scope['entity_id'].split(':')[-1], 'f14': '明确合成报价',
        'f2': 12.1, 'f18': 10, 'f124': 1792713600}]}},
        'https://example.invalid/followup-runtime-quote'))
    document['limitations'].append('明确合成报价，只验收确定条件与应用内投递链路。')
    return document

def reject_unbound(scope):
    raise AssertionError('财务复核应读取绑定来源；本夹具禁止真实 provider 调用')

api.collect = reject_unbound
with api.Service(config, researcher=quote) as service:
    def lifetime():
        sys.stdin.buffer.read()
        service.shutdown()
    threading.Thread(target=lifetime, daemon=True).start()
    print('ready', flush=True)
    service.serve_forever(poll_interval=.1)
