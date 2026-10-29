import hashlib
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from huohuo.server import Service


class DeliverablesApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = Service({'host': '127.0.0.1', 'port': 0, 'principal': 'alice',
                               'user_token': 'owner', 'worker_token': 'worker',
                               'database': str(Path(self.tmp.name) / 'db.sqlite')})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.server.mandates.store.close()
        self.tmp.cleanup()

    def call(self, path, body, token='owner', origin=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}
        if origin: headers['Origin'] = origin
        connection.request('POST', path, json.dumps(body).encode(), headers)
        response = connection.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        connection.close()
        return result

    def create(self, **extra):
        return self.call('/deliverables/create', {'session_id': 'chat', 'call_id': 'first',
            'spec': {'format': 'json', 'title': '测试', 'content_kind': 'model_analysis',
                     'evidence_ids': [], 'limitations': '用户提供/模型整理，未核验', 'tables': []}, **extra})

    def test_authenticated_binary_and_metadata_and_receipt(self):
        status, _, raw = self.create()
        self.assertEqual(status, 200, raw)
        saved = json.loads(raw)
        for part in ('file', 'metadata'):
            status, headers, content = self.call('/deliverables/download', {'id': saved['id'], 'part': part})
            self.assertEqual(status, 200)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertIn("filename*=UTF-8''", headers['Content-Disposition'])
            self.assertEqual(hashlib.sha256(content).hexdigest(), headers['X-Content-SHA256'])
            self.assertNotIn('owner', content.decode())
        status, _, raw = self.call('/deliverables/inspect', {'session_id': 'chat', 'source_call_id': 'first'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), saved)
        self.assertEqual(self.create()[2], json.dumps(saved, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())

    def test_auth_origin_session_and_parameter_boundaries(self):
        saved = json.loads(self.create()[2])
        for token in ('worker', 'wrong'):
            self.assertEqual(self.call('/deliverables/download', {'id': saved['id'], 'part': 'file'}, token=token)[0], 403)
        self.assertEqual(self.create(principal='bob')[0], 400)
        self.assertEqual(self.call('/deliverables/inspect', {'session_id': 'other', 'id': saved['id']})[0], 400)
        self.assertEqual(self.call('/deliverables/download', {'session_id': 'other', 'id': saved['id'], 'part': 'file'})[0], 400)
        self.assertEqual(self.call('/deliverables/download', {'id': '../db.sqlite', 'part': 'file'})[0], 400)
        self.assertEqual(self.call('/deliverables/download', {'id': saved['id'], 'part': 'file'}, origin='https://evil.invalid')[0], 403)
