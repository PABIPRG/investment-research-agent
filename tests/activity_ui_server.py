"""动态页专属新实例：真实 DSH/API/SQLite；仅合成数据，无研究 worker 与外发。"""
import json
import sys
import threading
import time
from pathlib import Path
from huohuo import server as api
from huohuo.research import snapshot
from huohuo.research_entities.bounded import collect
from huohuo.research_partner.commands import MandateCreateRequest

config = json.loads(Path(sys.argv[1]).read_text())
mode_file = Path(sys.argv[1]).parent / 'activity-mode.json'

def reject_provider(*args, **kwargs):
    raise AssertionError('动态验收禁止访问真实 provider')

api.collect = reject_provider
api.search_securities = reject_provider
original_get = api.Handler.do_GET

def controlled_get(self):
    try:
        mode = json.loads(mode_file.read_text())['mode'] if mode_file.exists() else 'normal'
        if self.path in ['/mandates', '/notifications']:
            self.authorized('user')
            if mode == 'partial' and self.path == '/mandates':
                return self.reply(200, {'items': [], 'next_cursor': 'synthetic-more'})
            if mode == 'empty':
                return self.reply(200, {'items': []})
            if self.path == '/mandates' and mode == 'mandates-error':
                return self.reply(503, {'error': 'synthetic_mandates_unavailable'})
            if self.path == '/notifications' and mode == 'notifications-error':
                return self.reply(503, {'error': 'synthetic_notifications_unavailable'})
    except PermissionError:
        return self.reply(401, {'error': 'invalid credentials'})
    return original_get(self)

api.Handler.do_GET = controlled_get

def seed(service):
    core, p = service.mandates, config['principal']
    core.entities.directory = lambda: {'status': 'ok', 'rows': [{'code': '600519', 'name': '贵州茅台'}], 'source': {'provider': '明确合成目录'}}
    scope = {'entity_id': 'SEC:CN:A:600519', 'exchange': 'SSE', 'operation': 'financial_summary', 'period': '20260630', 'metric': '营业总收入', 'basis': 'source_abstract'}
    core.service.create(core.context(p), MandateCreateRequest(
        goal='【合成验收】半年报复核范围待补充', scope=scope,
        subjects=[{'entity_id': scope['entity_id']}], basis={'entity_confirmation': {'label': '贵州茅台'}},
        requirements=[{'code': 'scope', 'detail': '请确认需要核对的研究范围'}],
        idempotency_key='activity-pending-001'))
    core.notifications.save(p, {'expected_revision': 0, 'enabled': True, 'channels': ['app'], 'timezone': 'Asia/Shanghai', 'quiet_hours': None})
    def create(key, goal, quote=False):
        resolved = core.entities.resolve(p, 'activity-uat', '600519股票')
        confirmed = core.entities.confirm(p, 'activity-uat', resolved['snapshot_id'], resolved['version'], {resolved['mentions'][0]['mention_id']: scope['entity_id']}, 'synthetic')
        selected = {'entity_id': scope['entity_id'], 'exchange': 'SSE', 'operation': 'quote_snapshot'} if quote else scope
        value = core.create(p, {'session_id': 'activity-uat', 'confirmation_id': confirmed['confirmations'][0]['confirmation_id'], 'request_key': key, 'goal': goal, 'scope': selected, 'contact_note': '明确合成验收，仅本实例应用内展示'})
        core.tick()
        return value, selected
    def finish(selected, summary, verdict='unknown'):
        job = core.repo.claim('activity-fixture')
        assert job is not None
        document = snapshot(selected, lambda _: ({'data': {'diff': [{'f12': '600519', 'f14': '贵州茅台', 'f2': 12.1, 'f18': 10, 'f124': int(core.repo.clock())}]}}, 'https://example.invalid/activity-quote')) if selected['operation'] == 'quote_snapshot' else collect(selected, lambda _: {'code': '600519', 'records': [{'指标': '营业总收入', '20260630': 100}]})
        document['limitations'].append('明确合成资料，不代表真实金融数据。')
        ev = core.repo.save_evidence(job['attempt_id'], job['lease_token'], document)
        core.repo.finish(job['attempt_id'], job['lease_token'], {'status': 'succeeded', 'execution_id': job['execution_id'], 'scope': selected, 'summary': summary, 'evidence_ids': [ev['evidence_id']], 'judgements': {'notable_change': {'judgement': verdict, 'reason': '合成验收：指标单位待核实时保留未知' if verdict == 'unknown' else '合成验收：明确条件满足，仅测试应用内记录', 'evidence_refs': [ev['evidence_id']]}}})
        core.tick()
    _, selected = create('activity-result-001', '【合成验收】半年报资料复核')
    finish(selected, '【合成验收】资料已整理，已保留引用来源；财务指标单位尚未核实，相关判断保持未知。')
    _, selected = create('activity-notice-001', '【合成验收】报价变化提醒', True)
    finish(selected, '【合成验收】报价资料已绑定，条件判断与本次执行关联；仅验证应用内提醒记录。', 'met')
    core.notifications.tick()
    # 保存一个失败、一个运行中和一个排队状态，均只写入本次新建实例。
    create('activity-failed-001', '【合成验收】上次资料复核失败')
    job = core.repo.claim('activity-fixture')
    core.repo.finish(job['attempt_id'], job['lease_token'], {'status': 'failed', 'error': '【合成验收】来源返回不足，未形成研究结论'})
    core.tick()
    create('activity-running-001', '【合成验收】正在核对资料')
    core.repo.claim('activity-fixture')
    create('activity-queued-001', '【合成验收】等待研究')
    Path(sys.argv[1]).parent.joinpath('activity-seed.json').write_text(json.dumps({'data': 'synthetic', 'external': False, 'mandates': len(core.list(p)['items'])}))

with api.Service(config, researcher=reject_provider) as service:
    seed(service)
    def lifetime():
        sys.stdin.buffer.read()
        service.shutdown()
    threading.Thread(target=lifetime, daemon=True).start()
    print('ready', flush=True)
    service.serve_forever(poll_interval=.1)
