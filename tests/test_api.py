import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from huohuo.server import Service


SCOPE = {"entity_id": "SEC:CN:A:600519", "exchange": "SSE", "operation": "quote_snapshot"}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Service({"host": "127.0.0.1", "port": 0, "principal": "owner", "user_token": "user-secret",
                                "worker_token": "worker-secret", "database": str(Path(self.temp.name) / "test.db")},
                               researcher=lambda scope: {"scope": scope, "status": "ok", "values": {"price": "12.1"}})
        self.thread = threading.Thread(target=self.service.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.service.server_port}"

    def tearDown(self):
        self.service.shutdown()
        self.service.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, body=None, token="user-secret", headers=None):
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def test_account_is_owner_authenticated_read_and_empty_values_are_zero(self):
        from unittest.mock import Mock
        self.service.market.query=Mock(side_effect=AssertionError('empty account must not query market'))
        self.assertEqual(self.call('/investment/account',token='worker-secret')[0],403)
        before=self.call('/investment')[1]
        status,value=self.call('/investment/account')
        self.assertEqual(status,200)
        self.assertEqual(value['holdings_count'],0)
        self.assertEqual(value['market_value']['value'],0)
        self.assertEqual(self.call('/investment')[1],before)
        self.service.market.query.assert_not_called()

    def test_security_search_auth_and_read_only(self):
        from unittest.mock import patch
        from huohuo.research_entities.security_search import reset_cache
        reset_cache()

        with patch("huohuo.research_entities.security_search.load_catalog", return_value=[{"code":"002518","name":"科士达"}]):
            self.assertEqual(403,self.call("/entities/search", {"query":"科士达"},token="worker-secret")[0])
            status,result=self.call("/entities/search", {"query":"科士达"})
            self.assertEqual(200,status)
            self.assertEqual("002518",result["candidates"][0]["code"])
            self.assertTrue(result["requires_confirmation"])
            self.assertEqual([],self.call("/mandates")[1]["items"])
            self.assertEqual([],self.call("/executions")[1]["executions"])
            self.assertEqual(400,self.call("/entities/search", {"query":"科士达","url":"https://evil.invalid"})[0])
        reset_cache()

    def test_risk_questionnaire_uses_user_api_and_persistent_preview_receipt(self):
        status, facts = self.call('/investment')
        self.assertEqual(status, 200)
        body = {'command': 'risk_profile', 'payload': {'tier': 'quick', 'answers': [
            {'qid': q['qid'], 'option': 2} for q in facts['risk_questionnaire']['quick']]}}
        self.assertEqual(self.call('/investment/preview', body, token='worker-secret')[0], 403)
        status, p = self.call('/investment/preview', body)
        self.assertEqual(status, 200)
        self.assertEqual(self.call('/investment')[1]['version'], 0)
        commit = {'preview_id': p['preview_id'], 'request_key': p['preview_id']}
        status, result = self.call('/investment/commit', commit)
        self.assertEqual(status, 200)
        self.assertEqual(result['facts']['risk_profile']['score'], 9)
        receipt = self.call('/investment/previews/' + p['preview_id'])[1]['receipt']
        self.assertEqual(receipt, result)
        self.assertEqual(self.call('/investment/commit', commit)[1], result)
        self.assertEqual(self.call('/investment')[1]['holdings_status'], 'not_recorded')
        self.assertEqual(self.call('/mandates')[1]['items'], [])

    def create(self):
        status, job = self.call("/executions", {"request_key": "create", "scope": SCOPE, "question": "查看当前报价"})
        self.assertEqual(201, status)
        return job

    def claim(self):
        status, attempt = self.call("/worker/claim", {"worker_id": "test-worker", "admission_policy": "hook-model-gate-v1"}, token="worker-secret")
        self.assertEqual(200, status)
        return attempt

    def test_identity_origin_and_role_boundaries(self):
        self.assertEqual(403, self.call("/health", token="bad")[0])
        self.assertEqual(403, self.call("/health", headers={"Origin": "https://attacker.invalid"})[0])
        self.assertEqual(403, self.call("/health", headers={"Host": "attacker.invalid"})[0])
        self.assertEqual(403, self.call("/worker/claim", {"worker_id": "fake"})[0])
        self.assertEqual(400, self.call("/executions", {"request_key": "k", "scope": SCOPE, "question": "q", "principal": "another"})[0])

    def test_recent_executions_are_bounded_and_principal_scoped(self):
        self.service.repo.create("another", "private", SCOPE, "不可见任务")
        self.assertEqual([], self.call("/executions")[1]["executions"])
        job = self.create()
        status, page = self.call("/executions")
        self.assertEqual(200, status)
        self.assertEqual([job], page["executions"])
        self.assertEqual(50, page["limit"])
        self.assertEqual(403, self.call("/executions", token="worker-secret")[0])

    def test_real_api_receipt_evidence_and_success(self):
        job, attempt = self.create(), self.claim()
        attempt_path = "/worker/attempts/" + attempt["attempt_id"]
        headers = {"X-Attempt-Token": attempt["lease_token"]}
        self.assertEqual(200, self.call(attempt_path + "/runtime", {"session_id": "s", "message_id": "m"}, "worker-secret", headers)[0])
        status, evidence = self.call("/attempts/" + attempt["attempt_id"] + "/research", {}, attempt["lease_token"])
        self.assertEqual(200, status)
        result = {"status": "succeeded", "execution_id": job["execution_id"], "scope": SCOPE,
                  "evidence_ids": [evidence["evidence_id"]], "summary": "已取得报价证据"}
        first = self.call(attempt_path + "/finish", result, "worker-secret", headers)
        self.assertEqual(200, first[0])
        self.assertEqual("succeeded", first[1]["status"])
        self.assertEqual(first, self.call(attempt_path + "/finish", result, "worker-secret", headers))
        events = self.call("/executions/" + job["execution_id"] + "/events")[1]
        self.assertIn("runtime.accepted", [event["kind"] for event in events])
        self.assertEqual(409, self.call("/attempts/" + attempt["attempt_id"] + "/research", {}, attempt["lease_token"])[0])

    def test_scope_cannot_be_replaced_and_capability_cannot_finish(self):
        self.create()
        attempt = self.claim()
        base = "/attempts/" + attempt["attempt_id"]
        self.assertEqual(400, self.call(base + "/research", {"scope": SCOPE}, attempt["lease_token"])[0])
        self.assertEqual(403, self.call("/worker" + base + "/finish", {"status": "failed", "error": "x"}, attempt["lease_token"])[0])

    def test_cancellation_during_collection_rejects_late_evidence(self):
        job, attempt = self.create(), self.claim()
        def collect(scope):
            self.service.repo.command("owner", job["execution_id"], "cancel", "cancel", attempt["revision"])
            return {"scope": scope, "status": "ok"}
        self.service.researcher = collect
        self.assertEqual(409, self.call("/attempts/" + attempt["attempt_id"] + "/research", {}, attempt["lease_token"])[0])
        self.assertEqual([], self.service.repo.evidence("owner", job["execution_id"]))

    def test_investment_preview_read_is_user_scoped_and_reconciles(self):
        status,p=self.call('/investment/preview',{'command':'holding','payload':{'ticker':'513130','name':'合成ETF','quantity':1000,'cost_price':None,'effective_at':'2026-01-01T00:00:00+08:00','reason':'期初快照'}})
        self.assertEqual(status,200)
        path='/investment/previews/'+p['preview_id']
        self.assertEqual(self.call(path,token='worker-secret')[0],403)
        self.assertEqual(self.call(path,token='bad')[0],403)
        self.assertEqual(self.call(path)[1]['after']['holdings'][0]['quantity_unit'],'份')
        saved=self.call('/investment/commit',{'preview_id':p['preview_id'],'request_key':p['preview_id']})[1]
        self.assertEqual(self.call(path)[1]['receipt'],saved)

    def test_discussion_subject_confirmation_is_authenticated_grouped_and_persistent(self):
        self.service.mandates.entities.directory=lambda:{'status':'ok','rows':[{'code':'000001','name':'平安银行'}],'source':{'provider':'fixture'}}
        body={'session_id':'group-http','query':'平安银行 000001 行情'}
        self.assertEqual(self.call('/entities/resolve',body,token='worker-secret')[0],403)
        status,r=self.call('/entities/resolve',body)
        self.assertEqual(status,200);self.assertEqual(len(r['discussion_subjects']),1)
        g=r['discussion_subjects'][0]
        answer={'session_id':'group-http','snapshot_id':r['snapshot_id'],'version':r['version'],'choices':{g['subject_id']:'SEC:CN:A:000001'},'source_call':'native-http'}
        self.assertEqual(self.call('/entities/confirm',answer|{'session_id':'other'})[0],400)
        self.assertEqual(self.call('/entities/confirm',answer|{'choices':{g['subject_id']:'CO:CN:A:000001'}})[0],400)
        status,saved=self.call('/entities/confirm',answer)
        self.assertEqual(status,200);self.assertEqual(len(saved['confirmations']),1)
        self.assertEqual(self.call('/entities/confirm',answer)[1],saved)
        again=self.call('/entities/resolve',body|{'query':'000001行情'})[1]
        self.assertFalse(again['requires_confirmation'])
        self.assertEqual(again['discussion_subjects'][0]['confirmation']['confirmation_id'],saved['confirmations'][0]['confirmation_id'])
        self.assertEqual(self.call('/mandates')[1]['items'],[])


if __name__ == "__main__":
    unittest.main()
