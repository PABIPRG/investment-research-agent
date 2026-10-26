"""新库渠道契约。所有传输拦截，不使用真实凭据。"""
import json
import unittest
from unittest.mock import Mock, patch
import test_followup as fixtures
from huohuo.contracts import Invalid
from huohuo.execution import Conflict

class ChannelTests(unittest.TestCase):
    def setUp(self):
        fixtures.FollowupTests.setUp(self)
        # 渠道测试需要确定判断；使用报价夹具，不绕过未知财务口径准入。
        self.scope=fixtures.QUOTE_SCOPE
    tearDown=fixtures.FollowupTests.tearDown
    create=fixtures.FollowupTests.create
    document=fixtures.FollowupTests.document
    result=fixtures.FollowupTests.result
    def settings(self,revision=0,**kw):
        return dict(expected_revision=revision,enabled=True,channels=['app','wecom'],timezone='Asia/Shanghai',quiet_hours=None,external={'wecom':{'key':'synthetic-key-only'}},**kw)
    def test_secret_redacted_revision_and_principal_isolation(self):
        n=self.core.notifications
        cfg=n.save('alice',self.settings())
        self.assertNotIn('synthetic-key-only',json.dumps(cfg))
        self.assertTrue(cfg['external']['wecom']['configured'])
        self.assertFalse(n.config('bob')['external']['wecom']['configured'])
        self.assertNotIn('synthetic-key-only',self.core.store._connect().execute('SELECT body FROM notification_config_audit').fetchone()[0])
        with self.assertRaises(Conflict):n.save('alice',self.settings())
        n.save('alice',self.settings(1)|{'external':{'wecom':{'key':''}}})
        self.assertTrue(n.config('alice')['external']['wecom']['configured'])
        with self.assertRaises(Invalid):n.save('alice',self.settings(2)|{'external':{'wecom':{'clear':True}}})
    def test_config_alone_does_not_expand_mandate(self):
        self.core.notifications.save('alice',self.settings());self.create();self.core.tick();self.result()
        self.assertEqual([r['channel'] for r in self.core.notifications.list('alice')['items']],['app'])
    def test_explicit_policy_multichannel_payload_and_no_replay(self):
        n=self.core.notifications;n.save('alice',self.settings());m=self.create()
        self.core.command('alice',m['mandate']['mandate_id'],'revise',{'request_key':'channel-choice','expected_revision':1,'expected_generation':0,'goal':m['revision']['goal'],'scope':m['revision']['scope'],'contact_note':'合成测试','contact_channels':['app','wecom']})
        with patch('huohuo.notifications.push.wecom.requests.post') as post:
            post.return_value.json.return_value={'errcode':0}
            post.return_value.status_code=200
            self.core.tick();self.result();n.tick()
            self.assertEqual(post.call_count,1)
            self.assertIn('合成',post.call_args.kwargs['json']['markdown']['content'])
        self.assertEqual({r['status'] for r in n.list('alice')['items']},{'delivered','accepted'})
    def test_missing_config_rejected(self):
        with self.assertRaises(Invalid):self.core.notifications.save('alice',self.settings()|{'external':{}})
    def test_unknown_secret_fields_rejected(self):
        with self.assertRaises(Invalid):self.core.notifications.save('alice',self.settings()|{'external':{'wecom':{'key':'x','url':'https://example.invalid'}}})

    def queue_external(self):
        n=self.core.notifications;n.save('alice',self.settings());m=self.create()
        self.core.command('alice',m['mandate']['mandate_id'],'revise',{'request_key':'channel-choice','expected_revision':1,'expected_generation':0,'goal':m['revision']['goal'],'scope':m['revision']['scope'],'contact_note':'合成测试','contact_channels':['app','wecom']})
        self.core.tick()
        with patch.object(n,'tick'):self.result()
        return m,next(r for r in n.list('alice')['items'] if r['channel']=='wecom')
    def test_target_change_cancels_old_queue_but_quiet_change_defers(self):
        _,q=self.queue_external();n=self.core.notifications
        n.save('alice',self.settings(1)|{'external':{},'quiet_hours':{'start':'00:00','end':'00:00'}})
        self.assertIsNone(n.reserve(q['decision_id'],'wecom'))
        self.assertEqual(next(r for r in n.list('alice')['items'] if r['channel']=='wecom')['status'],'deferred')
        n.save('alice',self.settings(2)|{'external':{'wecom':{'key':'new-synthetic-target'}}})
        self.core.store._connect().execute("UPDATE notification_queue SET eligible_at=0")
        self.assertIsNone(n.reserve(q['decision_id'],'wecom'))
        self.assertEqual(next(r for r in n.list('alice')['items'] if r['channel']=='wecom')['status'],'cancelled')
    def test_external_pause_and_receipts_are_isolated(self):
        m,q=self.queue_external();n=self.core.notifications
        app=n.reserve(q['decision_id']);n.settle(app,'delivered')
        self.core.command('alice',m['mandate']['mandate_id'],'pause',{'request_key':'pause-channel-test','expected_revision':2,'expected_generation':1})
        self.assertIsNone(n.reserve(q['decision_id'],'wecom'))
        self.assertEqual({r['status'] for r in n.list('alice')['items']},{'delivered','cancelled'})
    def test_uncertain_transport_never_replays_or_leaks_error(self):
        _,q=self.queue_external();n=self.core.notifications
        with patch('huohuo.notifications.push.wecom.requests.post',side_effect=RuntimeError('synthetic-key-only')) as post:
            n.tick();n.tick();self.assertEqual(post.call_count,1)
        rows=n.list('alice');self.assertNotIn('synthetic-key-only',json.dumps(rows))
        self.assertEqual(next(r for r in rows['items'] if r['channel']=='wecom')['status'],'unknown')
    def test_reused_serverchan_and_email_transports(self):
        from huohuo.notifications.channels import build_adapter
        with patch('huohuo.notifications.push.serverchan.requests.post') as post:
            post.return_value.status_code=200;post.return_value.json.return_value={'code':0}
            build_adapter('serverchan',{'sendkey':'synthetic-key'}).send({'title':'合成测试','content':'仅测试'})
            self.assertFalse(post.call_args.kwargs['allow_redirects'])
        with patch('huohuo.notifications.channels.smtplib.SMTP') as smtp:
            build_adapter('email',dict(host='smtp.example.invalid',port=587,username='test',password='synthetic-secret',sender='from@example.invalid')).send(dict(title='合成测试',content='仅测试',destination='to@example.invalid'))
            smtp.return_value.__enter__.return_value.starttls.assert_called_once()
            smtp.return_value.__enter__.return_value.send_message.assert_called_once()

if __name__=='__main__':unittest.main()
