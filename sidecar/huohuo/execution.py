from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .contracts import Invalid, canonical, scope as validate_scope, text
from .research_entities.bounded import validate_financial_document


class Conflict(RuntimeError):
    pass


class Missing(LookupError):
    pass


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Repository:
    """一个实例的执行台账。每个操作使用独立短事务，不持有外部调用。"""

    def __init__(self, path: Path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection(True) as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if "schema_info" in tables:
                if [r[0] for r in db.execute("SELECT version FROM schema_info")] != [1]:
                    raise RuntimeError("unsupported database schema")
                required = {"schema_info", "executions", "attempts", "commands", "evidence", "events"}
                if not required.issubset(tables):
                    raise RuntimeError("incomplete database schema")
            elif tables:
                raise RuntimeError("unversioned database is not an empty instance")
            else:
                schema = """
            CREATE TABLE IF NOT EXISTS executions (
              id TEXT PRIMARY KEY, principal TEXT NOT NULL, request_key TEXT NOT NULL,
              fingerprint TEXT NOT NULL, scope TEXT NOT NULL, question TEXT NOT NULL,
              status TEXT NOT NULL, revision INTEGER NOT NULL, fence INTEGER NOT NULL DEFAULT 0,
              current_attempt TEXT, result TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
              UNIQUE(principal, request_key));
            CREATE TABLE IF NOT EXISTS attempts (
              id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES executions(id),
              worker TEXT NOT NULL, fence INTEGER NOT NULL, token_hash TEXT NOT NULL,
              status TEXT NOT NULL, lease_until REAL NOT NULL, started_at REAL NOT NULL,
              runtime_receipt TEXT, result_hash TEXT, result_receipt TEXT);
            CREATE TABLE IF NOT EXISTS commands (
              principal TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, receipt TEXT NOT NULL,
              PRIMARY KEY(principal,key));
            CREATE TABLE IF NOT EXISTS evidence (
              id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(id),
              document TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT NOT NULL,
              kind TEXT NOT NULL, data TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS schema_info (version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_info VALUES (1);
                """
                # execute 保留当前事务；executescript 会提前提交，不能用于此初始化。
                for statement in schema.split(";"):
                    if statement.strip():
                        db.execute(statement)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def connection(self, write=False):
        if getattr(self, "core_store", None) is not None:
            with self.core_store.transaction():
                yield self.core_store._connect()
            return
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except BaseException:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def _event(self, db, execution_id, kind, data=None):
        db.execute("INSERT INTO events(execution_id,kind,data,created_at) VALUES(?,?,?,?)",
                   (execution_id, kind, canonical(data or {}), self.clock()))

    @staticmethod
    def _view(row):
        return {"execution_id": row["id"], "scope": json.loads(row["scope"]),
                "question": row["question"], "status": row["status"], "revision": row["revision"],
                "current_attempt": row["current_attempt"], "created_at": row["created_at"],
                "updated_at": row["updated_at"], "result": json.loads(row["result"]) if row["result"] else None}

    @staticmethod
    def _owned(db, principal, execution_id):
        row = db.execute("SELECT * FROM executions WHERE id=? AND principal=?", (execution_id, principal)).fetchone()
        if row is None:
            raise Missing("execution not found")
        return row

    def create(self, principal, key, scope, question):
        text(principal, "principal", 200)
        text(key, "request key", 200)
        scope = validate_scope(scope)
        return self._create(principal, key, scope, question)

    def create_strategy(self, principal, key, scope, question):
        from .research_partner.strategy_tasks import validate_execution_scope
        return self._create(principal, key, validate_execution_scope(scope), question)

    def _create(self, principal, key, scope, question):
        text(principal, "principal", 200)
        text(key, "request key", 200)
        text(question, "question")
        fingerprint = digest({"scope": scope, "question": question})
        with self.connection(True) as db:
            old = db.execute("SELECT * FROM executions WHERE principal=? AND request_key=?", (principal, key)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise Conflict("idempotency key reused with different content")
                return self._view(old)
            execution_id = str(uuid.uuid4())
            now = self.clock()
            db.execute("INSERT INTO executions(id,principal,request_key,fingerprint,scope,question,status,revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,1,?,?)",
                       (execution_id, principal, key, fingerprint, canonical(scope), question, "queued", now, now))
            self._event(db, execution_id, "execution.created")
            return self._view(self._owned(db, principal, execution_id))

    def recent(self, principal):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM executions WHERE principal=? AND COALESCE(json_extract(scope,'$.kind'),'research')!='strategy' ORDER BY created_at DESC, id DESC LIMIT 51",
                              (principal,)).fetchall()
            return {"executions": [self._view(row) for row in rows[:50]], "limit": 50, "has_more": len(rows) > 50}

    def get(self, principal, execution_id):
        with self.connection() as db:
            return self._view(self._owned(db, principal, execution_id))

    def history(self, principal, execution_id):
        with self.connection() as db:
            self._owned(db, principal, execution_id)
            return [{"seq": r["seq"], "kind": r["kind"], "data": json.loads(r["data"]), "created_at": r["created_at"]}
                    for r in db.execute("SELECT * FROM events WHERE execution_id=? ORDER BY seq", (execution_id,))]

    def command(self, principal, execution_id, action, key, expected_revision):
        text(key, "command key", 200)
        if action not in ("cancel", "retry") or type(expected_revision) is not int:
            raise Invalid("invalid command")
        fingerprint = digest([execution_id, action, expected_revision])
        with self.connection(True) as db:
            old = db.execute("SELECT * FROM commands WHERE principal=? AND key=?", (principal, key)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise Conflict("command key reused")
                return json.loads(old["receipt"])
            row = self._owned(db, principal, execution_id)
            if getattr(self, "core_store", None) is not None and db.execute("SELECT 1 FROM execution_jobs WHERE execution_id=?", (execution_id,)).fetchone():
                raise Conflict("委托研究须通过委托管理，不接受单次任务旁路命令")
            allowed = ("queued", "running") if action == "cancel" else ("failed", "interrupted")
            if row["revision"] != expected_revision or row["status"] not in allowed:
                raise Conflict("version or state conflict")
            status = "cancelled" if action == "cancel" else "queued"
            if row["current_attempt"]:
                db.execute("UPDATE attempts SET status=? WHERE id=? AND status='running'", (status, row["current_attempt"]))
            db.execute("UPDATE executions SET status=?,revision=revision+1,current_attempt=NULL,result=NULL,updated_at=? WHERE id=?",
                       (status, self.clock(), execution_id))
            self._event(db, execution_id, "execution." + action)
            receipt = self._view(self._owned(db, principal, execution_id))
            db.execute("INSERT INTO commands VALUES(?,?,?,?)", (principal, key, fingerprint, canonical(receipt)))
            return receipt

    def claim(self, worker, lease_seconds=30, *, lane="research", principal=None, execution_id=None):
        text(worker, "worker", 200)
        self._lease_duration(lease_seconds)
        with self.connection(True) as db:
            if lane not in ('research', 'strategy', 'strategy_compute', 'strategy_candidate'):
                raise Invalid('invalid execution lane')
            clause = "COALESCE(json_extract(scope,'$.kind'),'research') != 'strategy'" if lane == 'research' else "json_extract(scope,'$.kind')='strategy'"
            args = []
            if lane == 'strategy_compute': clause += " AND json_extract(scope,'$.action')!='candidate'"
            if lane == 'strategy_candidate': clause += " AND json_extract(scope,'$.action')='candidate'"
            if principal is not None: clause += ' AND principal=?'; args.append(principal)
            if execution_id is not None: clause += ' AND id=?'; args.append(execution_id)
            # 策略计算共享版本，按用户串行；这是同一队列的资源约束，不是另一个任务台账。
            if lane != 'research': clause += " AND NOT EXISTS (SELECT 1 FROM executions busy WHERE busy.principal=executions.principal AND busy.status='running' AND json_extract(busy.scope,'$.kind')='strategy')"
            order = "created_at,id" if lane == 'research' else "date(created_at,'unixepoch'), CASE json_extract(scope,'$.action') WHEN 'events' THEN 0 WHEN 'backtest' THEN 1 WHEN 'shadow' THEN 2 WHEN 'recall' THEN 3 WHEN 'evolve' THEN 4 ELSE 5 END,created_at,id"
            row = db.execute("SELECT * FROM executions WHERE status='queued' AND " + clause + " ORDER BY " + order + " LIMIT 1", args).fetchone()
            if row is None:
                return None
            attempt_id, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
            fence = row["fence"] + 1
            db.execute("INSERT INTO attempts(id,execution_id,worker,fence,token_hash,status,lease_until,started_at) VALUES(?,?,?,?,?,'running',?,?)",
                       (attempt_id, row["id"], worker, fence, digest(token), self.clock() + lease_seconds, self.clock()))
            db.execute("UPDATE executions SET status='running',revision=revision+1,fence=?,current_attempt=?,updated_at=? WHERE id=?",
                       (fence, attempt_id, self.clock(), row["id"]))
            self._event(db, row["id"], "attempt.claimed", {"attempt_id": attempt_id, "fence": fence})
            return {**self._view(self._owned(db, row["principal"], row["id"])), "attempt_id": attempt_id,
                    "lease_token": token, "fence": fence, "lease_until": self.clock() + lease_seconds}

    @staticmethod
    def _lease_duration(seconds):
        if type(seconds) is not int or not 5 <= seconds <= 120:
            raise Invalid("lease duration outside bounds")

    def _attempt(self, db, attempt_id, token):
        a = db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
        if a is None or not isinstance(token, str) or not secrets.compare_digest(a["token_hash"], digest(token)):
            raise Conflict("invalid execution capability")
        row = db.execute("SELECT * FROM executions WHERE id=?", (a["execution_id"],)).fetchone()
        return a, row

    def _active(self, db, attempt_id, token):
        a, row = self._attempt(db, attempt_id, token)
        if (a["status"] != "running" or row["status"] != "running" or a["lease_until"] <= self.clock()
                or row["current_attempt"] != a["id"] or row["fence"] != a["fence"]):
            raise Conflict("execution capability expired or revoked")
        if getattr(self, 'core_store', None) is not None:
            bound = db.execute('SELECT x.revision,x.generation,m.current_revision,m.status,g.generation AS current_generation FROM execution_jobs x JOIN mandates m USING(mandate_id) JOIN mandate_generation g USING(mandate_id) WHERE x.execution_id=?', (row['id'],)).fetchone()
            if bound and (bound['status'] != 'tracking' or bound['revision'] != bound['current_revision'] or bound['generation'] != bound['current_generation']):
                raise Conflict('mandate execution capability revoked')
        return a, row

    def active(self, attempt_id, token):
        with self.connection() as db:
            _, row = self._active(db, attempt_id, token)
            return self._view(row)

    def heartbeat(self, attempt_id, token, seconds=30):
        self._lease_duration(seconds)
        with self.connection(True) as db:
            self._active(db, attempt_id, token)
            until = self.clock() + seconds
            db.execute("UPDATE attempts SET lease_until=? WHERE id=?", (until, attempt_id))
            return {"lease_until": until}

    def runtime_receipt(self, attempt_id, token, receipt):
        if not isinstance(receipt, dict) or set(receipt) != {"session_id", "message_id"}:
            raise Invalid("invalid runtime receipt")
        for value in receipt.values():
            text(value, "runtime reference", 200)
        with self.connection(True) as db:
            a, row = self._active(db, attempt_id, token)
            encoded = canonical(receipt)
            if a["runtime_receipt"] and a["runtime_receipt"] != encoded:
                raise Conflict("runtime receipt already assigned")
            if not a["runtime_receipt"]:
                db.execute("UPDATE attempts SET runtime_receipt=? WHERE id=?", (encoded, attempt_id))
                self._event(db, row["id"], "runtime.accepted", receipt)
            return receipt

    def save_evidence(self, attempt_id, token, document):
        if not isinstance(document, dict) or len(canonical(document).encode()) > 100_000: raise Invalid("evidence exceeds bound")
        if {'evidence_id', 'execution_id', 'attempt_id', 'attempt_status'} & document.keys():
            raise Invalid("evidence cannot override program receipt")
        with self.connection(True) as db:
            _, row = self._active(db, attempt_id, token)
            if document.get("scope") != json.loads(row["scope"]):
                raise Conflict("evidence scope mismatch")
            binding = json.loads(row["scope"])
            if document.get("status") == "ok" and binding["operation"] == "financial_summary":
                validate_financial_document(document, binding)
            from .research_partner.market_sources import MARKET_OPERATIONS, validate_market_document
            if document.get('status')=='ok' and binding['operation'] in MARKET_OPERATIONS:
                validate_market_document(document,binding)
            evidence_id = digest([attempt_id, document])
            db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)", (evidence_id, attempt_id, canonical(document), self.clock()))
            return {"evidence_id": evidence_id, **document}

    def evidence(self, principal, execution_id):
        with self.connection() as db:
            self._owned(db, principal, execution_id)
            return [{"evidence_id": r["id"], "attempt_id": r["attempt_id"], "attempt_status": r["attempt_status"],
                     **json.loads(r["document"])} for r in db.execute(
                "SELECT e.*,a.status AS attempt_status FROM evidence e JOIN attempts a ON a.id=e.attempt_id WHERE a.execution_id=? ORDER BY e.created_at,e.id", (execution_id,))]

    def finish(self, attempt_id, token, result, *, _strategy_validated=False):
        if not isinstance(result, dict) or result.get("status") not in ("succeeded", "failed"):
            raise Invalid("invalid execution result")
        encoded, fingerprint = canonical(result), digest(result)
        if len(encoded.encode()) > 100_000:
            raise Invalid("result too large")
        with self.connection(True) as db:
            a, row = self._attempt(db, attempt_id, token)
            if json.loads(row["scope"]).get("kind") == "strategy" and not _strategy_validated:
                raise Conflict("strategy result requires domain validation")
            if a["result_hash"]:
                if a["result_hash"] != fingerprint:
                    raise Conflict("result already committed with different content")
                return json.loads(a["result_receipt"])
            self._active(db, attempt_id, token)
            binding = json.loads(row["scope"])
            if ("scope" in result and result["scope"] != binding) or ("execution_id" in result and result["execution_id"] != row["id"]):
                raise Conflict("result binding mismatch")
            if result["status"] == "succeeded":
                evidence_ids = result.get("evidence_ids")
                if (result.get("execution_id") != row["id"] or result.get("scope") != json.loads(row["scope"])
                        or not isinstance(evidence_ids, list) or not evidence_ids or len(evidence_ids) > 20):
                    raise Conflict("result binding or evidence missing")
                text(result.get("summary"), "summary", 20000)
                for evidence_id in evidence_ids:
                    text(evidence_id, "evidence id", 100)
                    found = db.execute("SELECT document FROM evidence WHERE id=? AND attempt_id=?", (evidence_id, attempt_id)).fetchone()
                    if not found or json.loads(found[0]).get("status") != "ok":
                        raise Conflict("result references unavailable evidence")
                    if binding['operation'] == 'financial_summary':
                        validate_financial_document(json.loads(found[0]), binding)
                    from .research_partner.market_sources import MARKET_OPERATIONS, validate_market_document
                    if binding['operation'] in MARKET_OPERATIONS:
                        validate_market_document(json.loads(found[0]),binding)
                self._validate_judgements(result, set(evidence_ids), binding)
            else:
                text(result.get("error"), "error", 2000)
            db.execute("UPDATE executions SET status=?,result=?,revision=revision+1,updated_at=? WHERE id=?",
                       (result["status"], encoded, self.clock(), row["id"]))
            receipt = self._view(self._owned(db, row["principal"], row["id"]))
            db.execute("UPDATE attempts SET status=?,result_hash=?,result_receipt=? WHERE id=?",
                       (result["status"], fingerprint, canonical(receipt), attempt_id))
            if getattr(self, "core_store", None) is not None and db.execute("SELECT 1 FROM execution_jobs WHERE execution_id=?", (row["id"],)).fetchone():
                db.execute("INSERT INTO result_outbox(attempt_id,result_hash,result) VALUES(?,?,?)", (attempt_id, fingerprint, encoded))
            self._event(db, row["id"], "execution." + result["status"], {"attempt_id": attempt_id})
            return receipt

    @staticmethod
    def _validate_judgements(result, evidence_ids, binding):
        # 条件服务优先读取 contact_suggestion，两个入口都必须检查。
        for container in (result, result.get('contact_suggestion', {})):
            if not isinstance(container, dict):
                raise Invalid('invalid contact suggestion')
            judgements = container.get('judgements', {})
            if not isinstance(judgements, dict):
                raise Invalid('invalid judgements')
            for judgement in judgements.values():
                if not isinstance(judgement, dict) or not isinstance(judgement.get('judgement'), str) or judgement['judgement'] not in {'met', 'unmet', 'unknown'}:
                    raise Invalid('invalid research judgement')
                refs = judgement.get('evidence_refs', [])
                if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in evidence_ids for ref in refs):
                    raise Conflict('judgement references unbound evidence')
                if judgement['judgement'] != 'unknown' and not refs:
                    raise Conflict('definite judgement requires evidence')
                if binding['operation'] == 'financial_summary' and judgement['judgement'] != 'unknown':
                    raise Conflict('financial source unit and basis are unverified; judgement must be unknown')

    def cancel_job(self, principal, execution_id):
        with self.connection(True) as db:
            row = self._owned(db, principal, execution_id)
            if row['status'] not in ('queued','running'): return self._view(row)
            db.execute("UPDATE attempts SET status='cancelled' WHERE execution_id=? AND status='running'",(execution_id,))
            db.execute("UPDATE executions SET status='cancelled',revision=revision+1,updated_at=? WHERE id=?",(self.clock(),execution_id))
            db.execute("UPDATE research_jobs SET status='cancelled',last_error='用户停止本次验证' WHERE job_id IN (SELECT job_id FROM execution_jobs WHERE execution_id=?)",(execution_id,))
            self._event(db,execution_id,'execution.cancel',{'reason':'user_cancelled_job'})
            return self._view(self._owned(db,principal,execution_id))

    def cancel_bound(self, mandate_id):
        with self.connection(True) as db:
            ids = 'SELECT execution_id FROM execution_jobs WHERE mandate_id=?'
            db.execute("UPDATE attempts SET status='cancelled' WHERE status='running' AND execution_id IN ("+ids+")", (mandate_id,))
            db.execute("UPDATE executions SET status='cancelled',revision=revision+1,updated_at=? WHERE status IN ('queued','running') AND id IN ("+ids+")", (self.clock(), mandate_id))
            db.execute("UPDATE research_jobs SET status='cancelled' WHERE mandate_id=? AND status IN ('pending','running','waiting_data')", (mandate_id,))
            db.execute("UPDATE strategy_runs SET status='cancelled',error='计划已停止或改约，未写入迟到结果',updated_at=? WHERE status='running' AND execution_id IN ("+ids+")", (self.clock(), mandate_id))

    def recover(self, *, abandoned=False):
        with self.connection(True) as db:
            rows = db.execute("SELECT e.id,a.id AS attempt_id FROM executions e JOIN attempts a ON a.id=e.current_attempt WHERE e.status='running' AND (a.lease_until<=? OR ?)", (self.clock(),int(abandoned))).fetchall()
            for row in rows:
                db.execute("UPDATE executions SET status='interrupted',revision=revision+1,updated_at=? WHERE id=?", (self.clock(), row["id"]))
                db.execute("UPDATE attempts SET status='interrupted' WHERE id=?", (row["attempt_id"],))
                self._event(db, row["id"], "execution.interrupted", {"attempt_id": row["attempt_id"], "reason": "lease_expired"})
            if getattr(getattr(self,'core_store',None),'strategies',None):
                self.core_store.strategies.tasks.route()
            return len(rows)
