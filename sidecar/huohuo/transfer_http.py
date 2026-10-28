"""旧数据仅由登录用户上传；操作会话、预览和确认回执严格绑定。"""
from .contracts import Invalid, text

def fields(value, required, optional=()):
    if not isinstance(value,dict) or set(value)-set(required)-set(optional) or set(required)-set(value):
        raise Invalid('导入请求字段无效')
    return value

def handle(handler,parts):
    if len(parts)!=2 or parts[0]!='transfer':return False
    handler.authorized('user')
    if handler.command!='POST':raise Invalid('导入仅接受 POST')
    operation=parts[1]
    body=handler.body(42*1024*1024 if operation=='upload' else 100_000)
    if not isinstance(body,dict):raise Invalid('导入请求无效')
    session=body.pop('session_id',None);text(session,'会话',200)
    service,principal=handler.server.transfer,handler.server.config['principal']
    if operation=='uploads':
        fields(body,());result=service.uploads(principal)
    elif operation in ('upload','prepare','commit'):
        result=getattr(service,operation)(principal,session,body)
    elif operation in ('status','cancel'):
        fields(body,('preview_id',));result=getattr(service,operation)(principal,session,body['preview_id'])
    elif operation=='changes':
        fields(body,('preview_id',),('category','offset','limit'))
        result=service.preview_changes(principal,session,**body)
    elif operation=='remove_upload':
        fields(body,('upload_id',));result=service.remove_upload(principal,session,body['upload_id'])
    elif operation=='archive':
        fields(body,(),('archive_id','category','offset','limit'));result=service.archive(principal,**body)
    else:raise Invalid('导入操作无效')
    handler.reply(200,result)
    return True
