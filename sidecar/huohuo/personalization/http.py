from ..contracts import Invalid

def handle(handler,parts):
    if not parts or parts[0]!='personalization':return False
    handler.authorized('user')
    service,principal=handler.server.personalization,handler.server.config['principal']
    if handler.command=='GET' and len(parts)==3 and parts[1]=='previews':
        handler.reply(200,service.inspect(principal,parts[2]));return True
    if handler.command!='POST' or len(parts)!=2:raise Invalid('偏好接口仅接受固定操作')
    body=handler.body()
    if parts[1]=='refresh':
        if body!={}:raise Invalid('资讯刷新不接受任意来源或标的')
        result=service.refresh_sources(principal,handler.server.market,handler.server.repo)
    elif parts[1]=='risk':
        if body!={}:raise Invalid('风险读取不接受外部画像或账户参数')
        result=service.risk(principal)
    elif parts[1]=='read':
        if not isinstance(body,dict) or set(body)-{'offset','days'}:raise Invalid('偏好查询参数无效')
        result=service.read(principal,**body)
    elif parts[1] in ('preview','commit','record'):result=getattr(service,parts[1])(principal,body)
    else:raise Invalid('偏好操作无效')
    handler.reply(200,result);return True
