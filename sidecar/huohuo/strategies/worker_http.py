"""供 server 在校验 worker token 后调用；页面 user token 不应路由到此处。"""
from ..contracts import Invalid
from .validation import exact


def handle(handler, parts):
    api = handler.server.strategies; principal = handler.server.config['principal']
    if handler.command != 'POST': raise Invalid('策略后台仅支持 POST')
    body = handler.body()
    if parts == ['strategies', 'tick']:
        exact(body, ()); return handler.reply(200, api.background_tick(principal))
    if parts == ['strategies', 'events']:
        exact(body, ('events',)); return handler.reply(200, api.ingest_events(principal, body['events']))
    if parts == ['strategies', 'planner', 'claim']:
        exact(body, ('worker_id',)); return handler.reply(200, api.planner_claim(principal, body['worker_id']))
    if len(parts) == 4 and parts[:2] == ['strategies', 'planner'] and parts[3] in ('heartbeat', 'finish'):
        token = handler.headers.get('X-Attempt-Token', '')
        if parts[3] == 'heartbeat':
            exact(body, ()); result = api.planner_heartbeat(principal, parts[2], token)
        else: result = api.planner_finish(principal, parts[2], token, body)
        return handler.reply(200, result)
    raise Invalid('未知策略后台操作')
