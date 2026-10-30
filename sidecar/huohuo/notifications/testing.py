"""显式确认的一条测试消息；复用渠道适配器，不制造委托或正式联系决定。"""
import uuid
from ..contracts import Invalid, text
from ..execution import Conflict, Missing, digest
from .configuration import CHANNELS, configured
from .channels import build_adapter
from .delivery import DeliveryError, DeliverySuppressed

TITLE='火火 · 测试提醒'
CONTENT='这是一条由你手动确认发送的测试提醒，用于核对已保存的提醒渠道。不包含研究结论，也不代表任何委托已触发。'

class NotificationTests:
    def __init__(self,notifications):
        self.owner=notifications;self.store=notifications.store;self.clock=notifications.core.repo.clock
    def recover(self,principal):
        self.store._connect().execute("UPDATE notification_tests SET status='unknown',detail='发送后未取得确定回执，禁止自动重发',updated_at=? WHERE principal=? AND status='in_flight' AND updated_at<=?",(self.clock(),principal,self.clock()-60))
    @staticmethod
    def view(row):
        return {k:row[k] for k in ('test_id','request_key','channel','target_summary','status','detail','created_at','updated_at','expires_at')}|{'ignores_quiet_hours':True}
    def row(self,principal,session,test_id):
        text(session,'会话',200);text(test_id,'测试编号',100)
        row=self.store._connect().execute('SELECT * FROM notification_tests WHERE test_id=? AND principal=? AND session=?',(test_id,principal,session)).fetchone()
        if not row:raise Missing('测试记录不存在或不属于当前会话')
        return row
    def inspect(self,principal,session,test_id):
        with self.store.transaction():
            self.recover(principal)
            return self.view(self.row(principal,session,test_id))
    def list(self,principal):
        with self.store.transaction():
            self.recover(principal)
            return {'items':[self.view(r) for r in self.store._connect().execute('SELECT * FROM notification_tests WHERE principal=? ORDER BY created_at DESC,test_id DESC LIMIT 20',(principal,))]}
    def cancel(self,principal,session,test_id):
        with self.store.transaction():
            row=self.row(principal,session,test_id)
            if row['status']=='prepared':
                self.store._connect().execute("UPDATE notification_tests SET status='cancelled',detail='已取消测试，未发送消息',updated_at=? WHERE test_id=?",(self.clock(),test_id))
            return self.view(self.row(principal,session,test_id))
    def eligible(self,principal,channel,revision):
        cfg=self.owner.config(principal)
        if cfg['revision']!=revision:raise Conflict('提醒配置已变化，请刷新后重新核对测试目标')
        if not cfg['enabled']:raise Invalid('请先开启提醒总开关，再发送测试提醒')
        if channel not in cfg['channels']:raise Invalid('请先启用所选提醒渠道')
        config=self.owner.channel_config(principal,channel) if channel!='app' else {}
        if channel!='app' and not configured(channel,config):raise Invalid('请先在安全表单补齐渠道配置')
        return config
    @staticmethod
    def target(channel,config):
        if channel=='app':return '当前火火网页内提示，并保存测试记录'
        if channel=='email':
            name,domain=config['destination'].rsplit('@',1)
            return name[:1]+'***@'+domain
        return '已保存的'+CHANNELS[channel]+('机器人' if channel=='wecom' else '接收渠道')
    def prepare(self,principal,session,body):
        if not isinstance(body,dict) or set(body)!={'channel','request_key','expected_revision'}:raise Invalid('测试参数无效')
        text(session,'会话',200);text(body['request_key'],'请求标识',200)
        channel=body['channel']
        if not isinstance(channel,str) or channel not in CHANNELS or type(body['expected_revision']) is not int or body['expected_revision']<0:raise Invalid('渠道或配置版本无效')
        fp=digest(body)
        with self.store.transaction():
            db=self.store._connect()
            prior=db.execute('SELECT * FROM notification_tests WHERE principal=? AND session=? AND request_key=?',(principal,session,body['request_key'])).fetchone()
            if prior:
                if prior['fingerprint']!=fp:raise Conflict('同一测试请求不能更换渠道或配置版本')
                self.recover(principal)
                return self.view(self.row(principal,session,prior['test_id']))
            config=self.eligible(principal,channel,body['expected_revision'])
            now=self.clock();test_id='NTT_'+uuid.uuid4().hex
            db.execute('INSERT INTO notification_tests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(test_id,principal,session,body['request_key'],fp,channel,body['expected_revision'],self.owner.channel_revision(principal,channel),self.target(channel,config),'prepared','等待你确认后发送一条测试提醒；本次忽略静默时间',now,now,now+300))
            return self.view(self.row(principal,session,test_id))
    def send(self,principal,session,body):
        if not isinstance(body,dict) or set(body)!={'test_id','request_key'}:raise Invalid('测试发送参数无效')
        text(body['request_key'],'请求标识',200)
        with self.store.transaction():
            self.recover(principal);row=self.row(principal,session,body['test_id'])
            if row['request_key']!=body['request_key']:raise Conflict('测试请求身份不匹配')
            if row['status']!='prepared':return self.view(row)
            if self.clock()>=row['expires_at']:raise Conflict('测试确认已过期，请重新核对')
            config=self.eligible(principal,row['channel'],row['config_revision'])
            if self.owner.channel_revision(principal,row['channel'])!=row['channel_revision']:raise Conflict('接收目标已变化，请重新核对')
            self.store._connect().execute("UPDATE notification_tests SET status='in_flight',detail='正在发送测试提醒，请勿重复提交',updated_at=? WHERE test_id=?",(self.clock(),row['test_id']))
        # 事务提交是发送起点。静默时间仅在此显式测试路径忽略；正式通知门禁不变。
        status,detail='delivered','测试提醒已保存，网页可显示提示；不代表已展示，不代表用户已读'
        if row['channel']!='app':
            try:
                adapter=self.owner.adapters.get(row['channel']) or build_adapter(row['channel'],config)
                receipt=adapter.send({'title':TITLE,'content':CONTENT,'destination':config.get('destination','configured')})
                if receipt is not None and receipt[0] not in {'accepted','delivered'}:
                    status,detail='unknown','渠道返回未确认的结果，禁止自动重发'
                else:status,detail='accepted','渠道已受理测试提醒，送达与已读尚未确认'
            except DeliverySuppressed:status,detail='failed','渠道未配置或未获授权，未完成测试发送'
            except DeliveryError as error:
                status='unknown' if error.outcome_uncertain else 'failed'
                detail='测试发送结果未知，禁止自动重发' if status=='unknown' else '测试发送失败，请核对渠道配置'
            except Exception:status,detail='unknown','测试发送结果未知，禁止自动重发'
        with self.store.transaction():
            self.store._connect().execute("UPDATE notification_tests SET status=?,detail=?,updated_at=? WHERE test_id=? AND status IN ('in_flight','unknown')",(status,detail,self.clock(),row['test_id']))
            return self.view(self.row(principal,session,row['test_id']))
