"""新版通知配置所有者；秘密不返回 UI、不进入审计正文。"""
import re
from ..contracts import Invalid

CHANNELS={'app':'应用内','wecom':'企业微信','serverchan':'Server 酱','email':'邮件'}
FIELDS={'wecom':('key',),'serverchan':('sendkey',),'email':('host','port','username','password','sender','destination')}
SECRETS={'key','sendkey','password'}

def validate_channels(value):
    if not isinstance(value,list) or not value or any(not isinstance(x,str) or x not in CHANNELS for x in value) or len(set(value))!=len(value):
        raise Invalid('请选择有效且不重复的通知渠道')
    return value

def configured(channel,config):
    required={'wecom':['key'],'serverchan':['sendkey'],'email':['host','port','sender','destination']}[channel]
    return all(config.get(k) for k in required) and (channel!='email' or not config.get('username') or bool(config.get('password')))

def public_config(channel,config):
    return {**{k:v for k,v in config.items() if k not in SECRETS},'configured':configured(channel,config),'secret_saved':{k:bool(config.get(k)) for k in FIELDS[channel] if k in SECRETS}}

def merge_config(channel,old,patch):
    if not isinstance(patch,dict) or set(patch)-set(FIELDS[channel])-{'clear'}:raise Invalid('渠道配置字段无效')
    if 'clear' in patch:
        if patch!={'clear':True}:raise Invalid('清除配置不能同时填写新值')
        return {}
    result=dict(old)
    for k,v in patch.items():
        if k=='port':
            if type(v) is not int or not 1<=v<=65535:raise Invalid('SMTP 端口必须在 1～65535 之间')
        elif not isinstance(v,str) or len(v)>1000 or '\n' in v or '\r' in v:raise Invalid('渠道字段格式无效')
        if k in SECRETS and v=='':continue
        result[k]=v
    if channel in {'wecom','serverchan'}:
        key=result.get(FIELDS[channel][0],'')
        if key and not re.fullmatch(r'[A-Za-z0-9_-]{1,256}',key):raise Invalid('请填写渠道密钥本身，不要填写完整网址')
    else:
        result={'host':'','port':587,'username':'','password':'','sender':'','destination':'',**result}
        if result['host'] and not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',result['host']):raise Invalid('SMTP 主机格式无效')
        for field in ('sender','destination'):
            if result[field] and not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+',result[field]):raise Invalid('请填写单个有效邮件地址')
    return result
