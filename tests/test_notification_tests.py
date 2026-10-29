"""单条测试消息使用隔离渠道替身，不发送真实通知。"""
import json
import unittest
from unittest.mock import Mock
import test_notification_channels as fixtures
from huohuo.contracts import Invalid
from huohuo.execution import Conflict, Missing
from huohuo.notifications.delivery import DeliveryError

class NotificationTestTests(unittest.TestCase):
    setUp=fixtures.ChannelTests.setUp
    tearDown=fixtures.ChannelTests.tearDown
    settings=fixtures.ChannelTests.settings
    def prepare(self,channel='wecom',key='test-one',session='chat'):
        return self.core.notifications.tests.prepare('alice',session,{'channel':channel,'request_key':key,'expected_revision':1})
    def send(self,p,session='chat'):
        return self.core.notifications.tests.send('alice',session,{'test_id':p['test_id'],'request_key':p['request_key']})
    def configure(self,**patch):
        return self.core.notifications.save('alice',self.settings()|patch)
    def test_prepare_no_send_quiet_bypass_and_single_persistent_receipt(self):
        n=self.core.notifications;adapter=Mock();adapter.send.return_value=None;n.adapters['wecom']=adapter
        self.configure(quiet_hours={'start':'00:00','end':'00:00'})
        p=self.prepare();adapter.send.assert_not_called();self.assertEqual(p['status'],'prepared')
        self.assertTrue(p['ignores_quiet_hours']);self.assertNotIn('synthetic-key-only',json.dumps(p))
        a=self.send(p);self.assertEqual(a['status'],'accepted');self.assertEqual(self.send(p),a)
        adapter.send.assert_called_once();self.assertEqual(len(n.tests.list('alice')['items']),1)
        self.assertEqual(self.core.store._connect().execute('SELECT COUNT(*) FROM mandates').fetchone()[0],0)
        self.assertEqual(self.core.store._connect().execute('SELECT COUNT(*) FROM notification_queue').fetchone()[0],0)
    def test_master_channel_configuration_and_version_gate(self):
        self.configure(enabled=False)
        with self.assertRaises(Invalid):self.prepare()
        n=self.core.notifications;n.save('alice',self.settings(1)|{'external':{}})
        with self.assertRaises(Conflict):self.prepare()
        with self.assertRaises(Invalid):n.tests.prepare('alice','chat',{'channel':'email','request_key':'mail','expected_revision':2})
        p=n.tests.prepare('alice','chat',{'channel':'wecom','request_key':'fresh','expected_revision':2})
        n.save('alice',self.settings(2)|{'external':{'wecom':{'key':'changed-target'}}})
        with self.assertRaises(Conflict):self.send(p)
    def test_unknown_never_replays_and_does_not_leak_transport_secret(self):
        self.configure();a=Mock();a.send.side_effect=RuntimeError('synthetic-key-only');self.core.notifications.adapters['wecom']=a
        p=self.prepare();result=self.send(p);self.assertEqual(result['status'],'unknown')
        self.assertEqual(self.send(p),result);self.assertEqual(a.send.call_count,1)
        self.assertNotIn('synthetic-key-only',json.dumps(self.core.notifications.tests.list('alice')))
    def test_session_owner_expiry_and_idempotency_boundaries(self):
        self.configure();p=self.prepare()
        with self.assertRaises(Missing):self.send(p,'another-chat')
        with self.assertRaises(Missing):self.core.notifications.tests.inspect('bob','chat',p['test_id'])
        with self.assertRaises(Conflict):self.prepare('app')
        self.core.store._connect().execute('UPDATE notification_tests SET expires_at=0')
        with self.assertRaises(Conflict):self.send(p)
    def test_in_flight_recovery_never_sends_again(self):
        self.configure();p=self.prepare();db=self.core.store._connect()
        db.execute("UPDATE notification_tests SET status='in_flight',updated_at=0")
        a=Mock();self.core.notifications.adapters['wecom']=a
        result=self.send(p);self.assertEqual(result['status'],'unknown');a.send.assert_not_called()
    def test_app_receipt_survives_reopen_and_write_contract_is_strict(self):
        self.configure();p=self.prepare('app');result=self.send(p);self.assertEqual(result['status'],'delivered')
        self.assertNotIn('已读',result['detail'].replace('不代表用户已读',''))
        with self.assertRaises(Invalid):self.core.notifications.tests.prepare('alice','chat',{'channel':'app','request_key':'bad','expected_revision':1,'destination':'other'})
        from huohuo.mandates import Mandates
        self.core.store.close();self.core=Mandates(self.repo,'test-instance')
        self.assertEqual(self.core.notifications.tests.inspect('alice','chat',p['test_id']),result)

    def test_concurrent_send_has_one_transport_start(self):
        import threading
        self.configure();p=self.prepare();started=threading.Event();release=threading.Event();results=[];errors=[]
        adapter=Mock()
        def transport(job):started.set();release.wait(3)
        adapter.send.side_effect=transport;self.core.notifications.adapters['wecom']=adapter
        def first():
            try:results.append(self.send(p))
            except Exception as error:errors.append(error)
            finally:self.core.store.close_current_connection()
        worker=threading.Thread(target=first);worker.start()
        try:
            self.assertTrue(started.wait(2))
            self.assertEqual(self.send(p)['status'],'in_flight')
        finally:release.set();worker.join(5)
        self.assertEqual(errors,[]);self.assertEqual(adapter.send.call_count,1)
        self.assertEqual(results[0]['status'],'accepted')

    def test_upgrade_from_previous_schema_preserves_notification_configuration(self):
        self.configure();before=self.core.notifications.config('alice');instance=self.core.instance;db=self.core.store._connect()
        db.execute('DROP TABLE notification_tests')
        db.execute("DELETE FROM schema_migrations WHERE version='020_notification_tests'")
        from huohuo.mandates import Mandates
        self.core.store.close();self.core=Mandates(self.repo,instance)
        self.assertEqual(self.core.notifications.config('alice'),before)
        self.assertEqual(self.core.notifications.tests.list('alice')['items'],[])
        backup=self.core.store.path.with_suffix(self.core.store.path.suffix+'.before-notification-tests')
        self.assertTrue(backup.exists(),'020迁移必须保留专属升级前备份，不能复用旧版本备份')

    def test_cancelled_preparation_cannot_later_send(self):
        self.configure();p=self.prepare();adapter=Mock();self.core.notifications.adapters['wecom']=adapter
        cancelled=self.core.notifications.tests.cancel('alice','chat',p['test_id'])
        self.assertEqual(cancelled['status'],'cancelled')
        self.assertEqual(self.send(p),cancelled);adapter.send.assert_not_called()
