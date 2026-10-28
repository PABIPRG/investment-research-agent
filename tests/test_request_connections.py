"""请求连接生命周期：真实 Handler 与临时库；socketpair 不监听端口。"""
import socket
import sqlite3
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from huohuo.execution import Repository
from huohuo.research_partner.adapters.sqlite_store import SqliteBusinessStore
from huohuo.research_partner.errors import StorageUnavailable
from huohuo.server import Handler


class RequestConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.temp.name) / 'business.sqlite')
        self.store = SqliteBusinessStore(self.repo.path)
        self.repo.core_store = self.store
        self.server = SimpleNamespace(
            server_port=18852, repo=self.repo, mandates=SimpleNamespace(store=self.store),
            config={'principal': 'fixture', 'worker_token': 'fixture-worker'})
        self.initial = len(self.store._connections)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def request(self):
        result, errors = [], []
        def handle():
            client, server = socket.socketpair()
            try:
                client.sendall(b'POST /worker/recover HTTP/1.0\r\nHost: 127.0.0.1:18852\r\n'
                              b'Authorization: Bearer fixture-worker\r\nContent-Type: application/json\r\n'
                              b'Content-Length: 2\r\n\r\n{}')
                Handler(server, ('127.0.0.1', 0), self.server)
                server.close()
                client.settimeout(1)
                response = b''
                while part := client.recv(4096):
                    response += part
                result.append(response)
            except BaseException as exc:
                errors.append(exc)
            finally:
                client.close(); server.close()
        thread = threading.Thread(target=handle)
        thread.start(); thread.join(5)
        self.assertFalse(thread.is_alive(), 'request did not finish')
        if errors: raise errors[0]
        return result[0]

    def test_completed_request_threads_do_not_retain_connections(self):
        for _ in range(40):
            self.assertTrue(self.request().startswith(b'HTTP/1.0 200'))
            self.assertEqual(len(self.store._connections), self.initial)

    def test_failed_request_rolls_back_releases_and_next_request_works(self):
        used = []
        def fail():
            with self.store.transaction():
                db = self.store._connect(); used.append(db)
                db.execute("INSERT INTO meta VALUES('request-failure','must-rollback')")
                raise RuntimeError('controlled failure')
        with patch.object(self.repo, 'recover', side_effect=fail):
            self.assertTrue(self.request().startswith(b'HTTP/1.0 500'))
        self.assertEqual(len(self.store._connections), self.initial)
        with self.assertRaises(sqlite3.ProgrammingError): used[0].execute('SELECT 1')
        self.assertIsNone(self.store._connect().execute("SELECT value FROM meta WHERE key='request-failure'").fetchone())
        self.assertTrue(self.request().startswith(b'HTTP/1.0 200'))

    def test_response_finish_error_also_releases_current_connection(self):
        handler = Handler.__new__(Handler); handler.server = self.server
        connection = self.store._connect()
        with patch.object(BaseHTTPRequestHandler, 'finish', side_effect=OSError('controlled disconnect')):
            with self.assertRaises(OSError): handler.finish()
        self.assertEqual(len(self.store._connections), 0)
        with self.assertRaises(sqlite3.ProgrammingError): connection.execute('SELECT 1')
        self.assertEqual(self.store._connect().execute('SELECT 1').fetchone()[0], 1)

    def test_nested_transaction_cannot_be_closed_mid_commit(self):
        with self.store.transaction():
            connection = self.store._connect()
            connection.execute("INSERT INTO meta VALUES('nested-owner','kept')")
            with self.store.transaction():
                with self.assertRaises(StorageUnavailable): self.store.close_current_connection()
                self.assertIs(self.store._connect(), connection)
        self.assertEqual(connection.execute("SELECT value FROM meta WHERE key='nested-owner'").fetchone()[0], 'kept')
        self.store.close_current_connection()
        self.assertEqual(self.store._connect().execute("SELECT value FROM meta WHERE key='nested-owner'").fetchone()[0], 'kept')

    def test_request_cleanup_does_not_close_other_worker_connection(self):
        ready, release = threading.Event(), threading.Event()
        errors = []
        def background():
            try:
                connection = self.store._connect(); ready.set()
                if not release.wait(5): raise RuntimeError('request did not release test worker')
                self.assertEqual(connection.execute('SELECT 1').fetchone()[0], 1)
                self.store.close_current_connection()
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=background); thread.start()
        try:
            self.assertTrue(ready.wait(2))
            self.assertTrue(self.request().startswith(b'HTTP/1.0 200'))
            self.assertEqual(len(self.store._connections), self.initial + 1)
        finally:
            release.set(); thread.join(5)
        if errors: raise errors[0]
        self.assertEqual(len(self.store._connections), self.initial)
