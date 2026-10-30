"""真实本机HTTP验证测试提醒的认证、会话和严格字段。"""
import unittest
import test_strategy_api as fixtures
class NotificationTestingApi(unittest.TestCase):
    setUp=fixtures.StrategyApi.setUp
    tearDown=fixtures.StrategyApi.tearDown
    call=fixtures.StrategyApi.call
    def test_prepare_send_and_read_share_persisted_owner_receipt(self):
        config={'expected_revision':0,'enabled':True,'channels':['app'],'timezone':'Asia/Shanghai','quiet_hours':{'start':'00:00','end':'00:00'}}
        self.assertEqual(self.call('/notifications/config',config)[0],200)
        body={'session_id':'chat','request_key':'one','channel':'app','expected_revision':1}
        self.assertEqual(self.call('/notifications/tests/prepare',body,token='wrong')[0],403)
        self.assertEqual(self.call('/notifications/tests/prepare',body|{'principal':'other'})[0],400)
        status,p=self.call('/notifications/tests/prepare',body);self.assertEqual(status,200)
        send={'session_id':'chat','test_id':p['test_id'],'request_key':p['request_key']}
        self.assertEqual(self.call('/notifications/tests/send',send|{'session_id':'other'})[0],404)
        self.assertEqual(self.call('/notifications/tests/send',send|{'destination':'other'})[0],400)
        status,r=self.call('/notifications/tests/send',send);self.assertEqual(status,200);self.assertEqual(r['status'],'delivered')
        self.assertEqual(self.call('/notifications/tests/send',send)[1],r)
        self.assertEqual(self.call('/notifications/tests')[1]['items'][0],r)
        self.assertEqual(self.call('/notifications')[1]['items'],[])

    def test_in_app_feed_is_owner_authenticated_and_test_only_after_confirmed_send(self):
        self.assertEqual(self.call('/notifications/in-app',token='wrong')[0],403)
        self.call('/notifications/config',{'expected_revision':0,'enabled':True,'channels':['app'],'timezone':'Asia/Shanghai','quiet_hours':None})
        _,p=self.call('/notifications/tests/prepare',{'session_id':'chat','request_key':'feed','channel':'app','expected_revision':1})
        status,feed=self.call('/notifications/in-app');self.assertEqual(status,200);self.assertEqual(feed['items'],[])
        self.call('/notifications/tests/send',{'session_id':'chat','test_id':p['test_id'],'request_key':'feed'})
        _,next_feed=self.call('/notifications/in-app')
        self.assertEqual(feed['scope'],next_feed['scope']);self.assertEqual(len(next_feed['items']),1)
        self.assertEqual(next_feed['items'][0]['kind'],'test')
        self.assertEqual(self.call('/notifications')[1]['items'],[])

    def test_in_app_read_does_not_wait_for_background_write_lock(self):
        import sqlite3,threading
        path=self.server.repo.path
        writer=sqlite3.connect(path,isolation_level=None)
        writer.execute('BEGIN IMMEDIATE')
        try:
            status,feed=self.call('/notifications/in-app')
            self.assertEqual(status,200);self.assertIn('scope',feed)
        finally:
            writer.execute('ROLLBACK');writer.close()
