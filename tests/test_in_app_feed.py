"""应用内呈现投影只承接现有送达记录，不发送、不扩大渠道或用户范围。"""
import unittest
import test_notification_channels as fixtures

class InAppFeedTests(unittest.TestCase):
    setUp=fixtures.ChannelTests.setUp
    tearDown=fixtures.ChannelTests.tearDown
    create=fixtures.ChannelTests.create
    document=fixtures.ChannelTests.document
    result=fixtures.ChannelTests.result
    settings=fixtures.ChannelTests.settings
    queue_external=fixtures.ChannelTests.queue_external
    def test_only_delivered_app_is_presented_and_owner_isolation_remains(self):
        m,external=self.queue_external();n=self.core.notifications
        self.assertEqual(n.in_app('alice')['items'],[])
        app=n.reserve(external['decision_id'],'app');n.settle(app,'delivered')
        other=n.reserve(external['decision_id'],'wecom');n.settle(other,'accepted')
        feed=n.in_app('alice')
        self.assertEqual(len(feed['items']),1)
        self.assertEqual(feed['items'][0]['kind'],'mandate')
        self.assertEqual(feed['items'][0]['mandate_id'],m['mandate']['mandate_id'])
        self.assertEqual(n.in_app('bob')['items'],[])
        self.assertNotEqual(n.in_app('bob')['scope'],feed['scope'])
        self.assertNotIn('synthetic-key-only',str(feed))
        self.assertEqual(n.in_app('alice'),feed)
