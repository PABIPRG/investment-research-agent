"""与页面/DSH 共用的实例认证接口；不接受浏览器身份或任意路径。"""
from ..contracts import Invalid
from .validation import exact

def handle(handler,parts):
    api=handler.server.strategies;principal=handler.server.config['principal']
    if handler.command=='GET' and parts==['strategies']:
        return handler.reply(200,api.read(principal))
    if handler.command!='POST':raise Invalid('不支持的策略请求')
    body=handler.body()
    if parts==['strategies','query']:
        exact(body,(),('strategy_id','request_key'));return handler.reply(200,api.read(principal,body.get('strategy_id'),body.get('request_key')))
    if parts==['strategies','cancel']:
        return handler.reply(200,api.cancel(principal,body))
    if parts in (['strategies','prepare'],['strategies','commit']):
        if not isinstance(body,dict) or 'session_id' not in body:raise Invalid('缺少会话绑定')
        session=body.pop('session_id')
        method=api.prepare if parts[-1]=='prepare' else api.commit
        return handler.reply(200,method(principal,session,body))
    raise Invalid('未知策略操作')
