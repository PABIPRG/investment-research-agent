"""明确标记的隔离界面验收数据；不调用模型或真实行情。"""
import json
import sys
import time
from pathlib import Path
from huohuo.execution import Repository
from huohuo.research import snapshot

config = json.loads(Path(sys.argv[1]).read_text())
clock = [time.time() - 300]
repo = Repository(Path(config['database']), clock=lambda: clock[0])
scope = {'entity_id': 'SEC:CN:A:600519', 'exchange': 'SSE', 'operation': 'quote_snapshot'}
principal = config['principal']

def create(key, question):
    clock[0] += 10
    return repo.create(principal, key, scope, '验收样本：' + question)

def document():
    return snapshot(scope, lambda _: ({'rc': 0, 'data': {'diff': [{'f12': '600519', 'f14': '界面验收合成样本', 'f2': 12.1, 'f18': 10, 'f124': 1792569600}]}}, 'https://example.invalid/ui-acceptance'))

success = create('success', '复核一次报价并保留历史证据')
old = repo.claim('ui-fixture')
repo.save_evidence(old['attempt_id'], old['lease_token'], document())
failed = repo.finish(old['attempt_id'], old['lease_token'], {'status': 'failed', 'error': '验收样本：首轮失败'})
repo.command(principal, success['execution_id'], 'retry', 'retry-one', failed['revision'])
job = repo.claim('ui-fixture')
repo.runtime_receipt(job['attempt_id'], job['lease_token'], {'session_id': 'fixture-session', 'message_id': 'fixture-message'})
evidence = repo.save_evidence(job['attempt_id'], job['lease_token'], document())
repo.finish(job['attempt_id'], job['lease_token'], {'status': 'succeeded', 'execution_id': job['execution_id'], 'scope': scope, 'evidence_ids': [evidence['evidence_id']], 'summary': '界面验收使用的合成结果：报价 12.10 元/股，相对昨收上涨 21.00%。此记录不代表真实行情或模型研究。'})
create('failed', '查看采集失败的原因')
job = repo.claim('ui-fixture')
repo.finish(job['attempt_id'], job['lease_token'], {'status': 'failed', 'error': '验收样本：行情源暂时不可用，未得到可用证据。'})
create('interrupted', '验证中断状态')
repo.claim('ui-fixture', lease_seconds=5)
clock[0] += 6
repo.recover()
cancelled = create('cancelled', '验证已取消状态')
repo.command(principal, cancelled['execution_id'], 'cancel', 'cancel-one', cancelled['revision'])
create('running', '检查正在执行的研究')
repo.claim('ui-fixture', lease_seconds=120)
create('queued', '等待执行的长中文问题：' + '请核对数据来源、时间与变化原因。' * 8)
other = repo.create('different-principal', 'other', scope, '不应在当前用户界面出现')
print(json.dumps({'success_id': success['execution_id'], 'count': len(repo.recent(principal)['executions'])}))
