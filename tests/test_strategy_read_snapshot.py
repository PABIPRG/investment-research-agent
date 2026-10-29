"""策略只读页面不等待其他连接的写锁；不访问任何外部来源。"""
import sqlite3
import threading
import unittest
import test_strategy_domain as fixtures

class StrategyReadSnapshotTests(unittest.TestCase):
    setUp = fixtures.StrategyDomainTests.setUp
    tearDown = fixtures.StrategyDomainTests.tearDown

    def test_page_read_completes_while_another_connection_holds_write_lock(self):
        self.service.read('alice')
        writer=sqlite3.connect(self.repo.path,isolation_level=None)
        done=threading.Event();result=[];errors=[]
        def read():
            try:result.append(self.service.read('alice'))
            except Exception as error:errors.append(error)
            finally:
                self.core.store.close_current_connection()
                done.set()
        writer.execute('BEGIN IMMEDIATE')
        thread=threading.Thread(target=read);thread.start()
        try:
            completed=done.wait(1)
        finally:
            writer.execute('ROLLBACK');writer.close();thread.join(6)
        self.assertTrue(completed,'只读页面被另一个连接的写锁阻塞')
        self.assertEqual(errors,[])
        self.assertEqual(result[0]['strategies'],[])
        self.assertEqual(self.calls,[])
