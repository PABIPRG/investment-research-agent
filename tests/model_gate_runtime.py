"""隔离 Service 与真实 Node worker 的受控验收；启动时显式传入本次编译目录。"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from huohuo.server import Service
from huohuo.execution import Repository
from huohuo.research_partner.market_sources import collect_market
from test_market_integration import Market, SCOPE


def worker(root, config, library):
    path = root / 'fixture.json'
    path.write_text(json.dumps(config)); path.chmod(0o600)
    value = subprocess.run(['node', str(Path(__file__).with_name('model-gate-runtime.mjs')), library, str(path)],
                           capture_output=True, text=True, check=True, timeout=15)
    return json.loads(value.stdout)


def run(library):
    report = []
    for case, expected in [('orphan', 0), ('numeric_unmet', 0), ('numeric_met', 0),
                           ('unknown_source', 0), ('semantic_initial', 1), ('semantic_source', 1), ('pause_before_submit', 0)]:
        with tempfile.TemporaryDirectory(prefix='huohuo-gate-uat-') as folder:
            root = Path(folder)
            config = dict(host='127.0.0.1', port=0, principal='fixture-owner', user_token='synthetic-user-only',
                          worker_token='synthetic-worker-only', database=str(root/'business.db'),
                          dsh_home=str(root), workspace=str(root), provider='fixture', model='fixture')
            service = Service(config); config['port'] = service.server_port
            core = service.mandates; market = Market()
            service.market.query = market.query
            core.entities.directory = lambda: dict(status='ok', rows=[dict(code='600519', name='合成公司')], source=dict(provider='fixture'))
            thread = threading.Thread(target=service.serve_forever, daemon=True); thread.start()
            try:
                if case == 'orphan':
                    service.repo.create(config['principal'], 'orphan', SCOPE, '旧任务没有可信触发')
                else:
                    r = core.entities.resolve(config['principal'], 'fixture', '600519行情')
                    c = core.entities.confirm(config['principal'], 'fixture', r['snapshot_id'], r['version'],
                                              {r['mentions'][0]['mention_id']: SCOPE['entity_id']}, 'fixture')
                    body = dict(request_key='uat-create', scope=SCOPE, goal='受控委托门禁验收', contact_note='仅应用内',
                                session_id='fixture', confirmation_id=c['confirmations'][0]['confirmation_id'])
                    if case.startswith('numeric') or case == 'unknown_source':
                        body['contact_rule'] = dict(mode='condition', condition=dict(type='numeric', metric='price', operator='>', threshold=100))
                    view = core.create(config['principal'], body)
                    if case == 'numeric_met': market.price = 110
                    if case == 'unknown_source': service.market.query = lambda _: dict(status='unavailable')
                    if case == 'pause_before_submit':
                        config['pause'] = dict(mandate_id=view['mandate']['mandate_id'],
                            body=dict(request_key='uat-pause', expected_revision=1, expected_generation=0))
                    if case == 'semantic_source':
                        initial = worker(root, config, library)
                        assert initial['prompted'] == 1, initial
                        core.tick()
                        market.price = 110
                        core.sources.accept(config['principal'], collect_market(SCOPE, market))
                result = worker(root, config, library)
                assert result['prompted'] == expected, (case, result)
                if not expected and case != 'pause_before_submit': assert result['constructed'] == 0, result
                core.tick()
                state = service.repo.get(config['principal'], result['execution_id'])['status']
                assert state == ('cancelled' if case == 'pause_before_submit' else 'failed' if case in {'orphan', 'unknown_source'} else 'succeeded'), (case, state)
                # 新会话回读独立数据库，证明准入与提交预占并非仅内存或日志。
                reader = Repository(root/'business.db')
                history = reader.history(config['principal'], result['execution_id'])
                reservations = [x for x in history if x['kind'] == 'model.submission_reserved']
                assert len(reservations) == expected, (case, reservations)
                if expected or case.startswith('numeric'):
                    repeat = worker(root, config, library)
                    assert repeat.get('no_job'), (case, repeat)
                report.append(dict(case=case, status='passed', model_prompts=result['prompted'], runtime_starts=result['started'],
                                   execution_status=state, persisted_reservations=len(reservations)))
            finally:
                service.shutdown(); service.server_close(); thread.join(); core.store.close()
    return dict(status='passed', cases=report, provider='synthetic-only', sources='synthetic-only', external_delivery=False)


if __name__ == '__main__':
    result = run(sys.argv[1])
    output = os.environ.get('HUOHUO_MODEL_GATE_REPORT')
    if output: Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
