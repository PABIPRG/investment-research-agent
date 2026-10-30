import json
import hashlib
import uuid
from datetime import datetime, timezone
from .configuration import CHANNELS, FIELDS, configured, public_config, merge_config, validate_channels
from .channels import build_adapter
from .delivery import DeliveryError, DeliverySuppressed
from .market_gate import current_for_delivery
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from ..contracts import Invalid, canonical
from ..execution import Conflict
from ..research_partner.models import NotificationPreferences
from ..research_partner.contact_policy import parse_quiet_hours, quiet_hours_until, parse_contact_policy

class Notifications:
    def __init__(self, core, adapters=None):
        self.core=core;self.store=core.store
        core.repo.path.chmod(0o600)
        self.adapters=adapters or {} # 不读取旧凭据，不装配旧 dispatcher。
        from .testing import NotificationTests
        self.tests=NotificationTests(self)

    def channel_config(self, principal, channel):
        row=self.store._connect().execute('SELECT config FROM notification_channels WHERE principal=? AND channel=?',(principal,channel)).fetchone()
        return json.loads(row[0]) if row else {}

    def channel_revision(self, principal, channel):
        row=self.store._connect().execute('SELECT revision FROM notification_channels WHERE principal=? AND channel=?',(principal,channel)).fetchone()
        return row[0] if row else 0

    def config(self, principal):
        row=self.store._connect().execute('SELECT * FROM notification_config WHERE principal=?',(principal,)).fetchone()
        prefs=self.store.get_notification_preferences(principal,self.core.instance)
        return {'revision':row['revision'] if row else 0,'enabled':bool(row['enabled']) if row else False,
                'channels':prefs.channels if prefs else ['app'],'timezone':prefs.timezone if prefs else 'Asia/Shanghai',
                'quiet_hours':prefs.quiet_hours if prefs else None,'external':{c:public_config(c,self.channel_config(principal,c)) for c in FIELDS},'external_status':'渠道须在每项委托中明确选择，保存配置不会自动外发'}

    def save(self, principal, body):
        if not isinstance(body,dict) or set(body)-{'external'}!={'expected_revision','enabled','timezone','quiet_hours','channels'}:raise Invalid('配置字段不完整')
        if type(body['enabled']) is not bool or type(body['expected_revision']) is not int:raise Invalid('配置类型错误')
        validate_channels(body['channels'])
        external=body.get('external',{})
        if not isinstance(external,dict) or set(external)-set(FIELDS):raise Invalid('不支持的外部渠道')
        try:ZoneInfo(body['timezone'])
        except (ZoneInfoNotFoundError,TypeError,ValueError):raise Invalid('时区无效')
        try:quiet=parse_quiet_hours(body['quiet_hours']) if body['quiet_hours'] is not None else None
        except ValueError as exc:raise Invalid(str(exc)) from None
        with self.store.transaction():
            current=self.config(principal)
            if current['revision']!=body['expected_revision']:raise Conflict('配置已变化，请刷新后重试')
            configs={c:merge_config(c,self.channel_config(principal,c),external.get(c,{})) for c in FIELDS}
            for c in body['channels']:
                if c!='app' and not configured(c,configs[c]):raise Invalid(f'{CHANNELS[c]}配置不完整，请补齐后启用')
            for c,cfg in configs.items():
                self.store._connect().execute('INSERT INTO notification_channels VALUES(?,?,?,1) ON CONFLICT(principal,channel) DO UPDATE SET config=excluded.config,revision=notification_channels.revision+CASE WHEN notification_channels.config!=excluded.config THEN 1 ELSE 0 END',(principal,c,canonical(cfg)))
            now=datetime.now(timezone.utc);version=current['revision']+1;db=self.store._connect()
            self.store.save_notification_preferences(NotificationPreferences(principal_id=principal,instance_id=self.core.instance,timezone=body['timezone'],quiet_hours=quiet,channels=body['channels'],updated_at=now))
            db.execute('INSERT INTO notification_config VALUES(?,?,?,?) ON CONFLICT(principal) DO UPDATE SET revision=excluded.revision,enabled=excluded.enabled,updated_at=excluded.updated_at',(principal,version,int(body['enabled']),now.isoformat()))
            db.execute('INSERT INTO notification_config_audit(principal,revision,body,created_at) VALUES(?,?,?,?)',(principal,version,canonical({**body,'external':{c:public_config(c,cfg) for c,cfg in configs.items()}}),now.isoformat()))
        return self.config(principal)

    def enqueue(self, decision, generation):
        if decision.decision!='send' and not (decision.decision=='defer' and decision.reason_code=='quiet_hours'):return
        mandate=self.store.get_mandate_internal(decision.mandate_id)
        revision=self.store.get_revision(decision.mandate_id,decision.mandate_revision)
        policy=parse_contact_policy(revision.contact_policy)
        cfg=self.config(mandate.principal_id)
        now=self.core.repo.clock()
        for channel in policy.channels:
            if channel not in cfg['channels'] or channel not in CHANNELS:continue
            self.store._connect().execute("INSERT OR IGNORE INTO notification_queue(decision_id,principal,mandate_id,revision,generation,channel,status,eligible_at,expires_at,updated_at,config_revision) VALUES(?,?,?,?,?,?,'queued',?,?,?,?)",(decision.decision_id,mandate.principal_id,mandate.mandate_id,decision.mandate_revision,generation,channel,decision.eligible_at.timestamp() if decision.eligible_at else now,decision.expires_at.timestamp() if decision.expires_at else now+86400,now,self.channel_revision(mandate.principal_id,channel)))

    def list(self, principal):
        rows=self.store._connect().execute('SELECT q.*,d.reason_code,d.condition_result,d.detail AS decision_detail,d.evidence_ref FROM notification_queue q JOIN contact_decisions d USING(decision_id) WHERE principal=? ORDER BY updated_at DESC LIMIT 200',(principal,)).fetchall()
        return {'items':[dict(r) for r in rows]}

    def in_app(self, principal):
        with self.store.read_snapshot():
            return self._in_app(principal)

    def _in_app(self, principal):
        # Read projection only: delivery eligibility remains owned by reserve/send.
        items=[]
        for row in self.list(principal)['items']:
            if row['channel']!='app' or row['status']!='delivered':continue
            revision=self.store.get_revision(row['mandate_id'],row['revision'])
            items.append({'id':'decision:'+row['decision_id'],'kind':'mandate','title':revision.goal,'body':row['decision_detail'],'mandate_id':row['mandate_id'],'decision_id':row['decision_id'],'created_at':row['updated_at']})
        for row in self.store._connect().execute("SELECT * FROM notification_tests WHERE principal=? AND channel='app' AND status='delivered' ORDER BY created_at DESC LIMIT 20",(principal,)):
            if row['channel']=='app' and row['status']=='delivered':
                from .testing import TITLE,CONTENT
                items.append({'id':'test:'+row['test_id'],'kind':'test','title':TITLE,'body':CONTENT,'created_at':row['updated_at']})
        scope=hashlib.sha256((self.core.instance+':'+principal).encode()).hexdigest()[:32]
        return {'scope':scope,'items':sorted(items,key=lambda x:(x['created_at'],x['id']))}

    def reserve(self, decision_id, channel='app'):
        # 与暂停/撤权/配置命令共享 BEGIN IMMEDIATE；commit 是发送起点。
        with self.store.transaction():
            db=self.store._connect();now=self.core.repo.clock()
            q=db.execute('SELECT * FROM notification_queue WHERE decision_id=? AND channel=?',(decision_id,channel)).fetchone()
            if not q or q['status'] not in {'queued','deferred','retry'} or q['eligible_at']>now:return None
            m=self.store.get_mandate_internal(q['mandate_id']);cfg=self.config(q['principal'])
            generation=db.execute('SELECT generation FROM mandate_generation WHERE mandate_id=?',(q['mandate_id'],)).fetchone()
            reason=None
            if not m or m.status!='tracking' or m.current_revision!=q['revision'] or not generation or generation[0]!=q['generation']:reason='委托状态、版本或取消代次已改变'
            elif now>=q['expires_at']:reason='联系许可已过期'
            elif not cfg['enabled']:reason='用户已关闭提醒'
            elif q['channel'] not in cfg['channels']:reason='渠道已禁用'
            elif q['channel']!='app' and q['config_revision']!=self.channel_revision(q['principal'],q['channel']):reason='渠道配置已变化，请等待新的联系决定'
            elif q['channel']!='app' and not configured(q['channel'],self.channel_config(q['principal'],q['channel'])):reason='渠道配置已清除'
            else:
                policy=parse_contact_policy(self.store.get_revision(m.mandate_id,m.current_revision).contact_policy)
                if q['channel'] not in policy.channels:reason='渠道不在委托许可内'
            if reason is None and not current_for_delivery(self.core, decision_id):
                reason="市场资料已过时或证据不可核对，取消本次发送"
            if reason is None and getattr(self.core,'position_risk',None):
                reason=self.core.position_risk.reason(q['mandate_id'],exclude_decision=decision_id)
            if reason:
                db.execute("UPDATE notification_queue SET status='cancelled',detail=?,updated_at=? WHERE decision_id=? AND channel=?",(reason,now,decision_id,channel));return None
            quiet=cfg['quiet_hours']
            until=quiet_hours_until(quiet,datetime.fromtimestamp(now,timezone.utc),cfg['timezone']) if quiet else None
            if until:
                db.execute("UPDATE notification_queue SET status='deferred',eligible_at=?,detail='处于静默时段',updated_at=? WHERE decision_id=? AND channel=?",(until.timestamp(),now,decision_id,channel));return None
            permit=uuid.uuid4().hex
            db.execute("UPDATE notification_queue SET status='in_flight',permit_id=?,attempts=attempts+1,updated_at=? WHERE decision_id=? AND channel=?",(permit,now,decision_id,channel))
            result=dict(q)|{'permit_id':permit,'attempts':q['attempts']+1}
            if channel!='app':
                decision=self.store._connect().execute('SELECT detail,evidence_ref FROM contact_decisions WHERE decision_id=?',(decision_id,)).fetchone()
                result.update(channel_config=self.channel_config(q['principal'],channel),title='火火：'+self.store.get_revision(m.mandate_id,m.current_revision).goal,content=f"{decision['detail']}\n委托：{m.mandate_id}\n联系记录：{decision_id}\n证据：{decision['evidence_ref'] or '请在应用内核对'}\n请打开火火的消推配置，回访委托与证据。")
                result['destination']=result['channel_config'].get('destination','configured')
            return result

    def settle(self, permit, status, detail=''):
        if status not in {'accepted','delivered','unknown','failed','retry'}:raise Invalid('回执状态无效')
        with self.store.transaction():
            db=self.store._connect();now=self.core.repo.clock()
            q=db.execute('SELECT * FROM notification_queue WHERE decision_id=? AND permit_id=? AND channel=?',(permit['decision_id'],permit['permit_id'],permit['channel'])).fetchone()
            if not q or q['status'] not in {'in_flight','unknown','accepted'}:return
            if status=='retry' and q['attempts']>=3:status='failed'
            db.execute('UPDATE notification_queue SET status=?,detail=?,eligible_at=?,updated_at=? WHERE decision_id=? AND channel=?',(status,detail,now+60*q['attempts'],now,q['decision_id'],q['channel']))
            db.execute('INSERT INTO notification_receipts(decision_id,permit_id,status,detail,created_at,channel) VALUES(?,?,?,?,?,?)',(q['decision_id'],q['permit_id'],status,detail,now,q['channel']))

    def tick(self):
        with self.store.transaction():
            db=self.store._connect();now=self.core.repo.clock()
            db.execute("UPDATE notification_queue SET status='unknown',detail='发送后未取得确定回执，禁止自动重发',updated_at=? WHERE status='in_flight' AND updated_at<?",(now,now-60))
            ids=[(r[0],r[1]) for r in db.execute("SELECT decision_id,channel FROM notification_queue WHERE status IN ('queued','deferred','retry') AND eligible_at<=?",(now,))]
        for did,channel in ids:
            permit=self.reserve(did,channel)
            if not permit:continue
            if permit['channel']=='app':self.settle(permit,'delivered','已保存到应用内回访；不代表用户已读')
            else:
                adapter=self.adapters.get(permit['channel']) or build_adapter(permit['channel'],permit['channel_config'])
                if adapter is None:self.settle(permit,'failed','渠道未配置');continue
                try:
                    receipt=adapter.send(permit)
                    # 旧适配器成功返回 None 只证明受理，不能冒充送达。
                    status,detail=receipt if receipt is not None else ('accepted','渠道已受理，送达未确认')
                    self.settle(permit,status,detail)
                except DeliverySuppressed:self.settle(permit,'failed','渠道未配置或未获授权')
                except DeliveryError as exc:
                    self.settle(permit,'unknown' if exc.outcome_uncertain else 'retry' if exc.retryable else 'failed',exc.code)
                except Exception:self.settle(permit,'unknown','渠道结果未知，需对账，禁止盲重发')
