"""仅监听 loopback 的实例 API；身份来自实例凭据，不接受请求自行声明。"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .contracts import Invalid, canonical
from .execution import Conflict, Missing, Repository
from .research import snapshot
from .research_entities.bounded import collect
from .research_entities.resolution import resolve
from .research_entities.security_search import search as search_securities
from .mandates import Mandates
from .investment.service import Investment
from .investment.collections import CollectionProvider
from .research_entities.tool_bridge import ResearchToolBridge
from .strategies.service import Strategies
from .strategies.http import handle as strategy_http
from .runtime_services import install as install_runtime, handle as runtime_http
from .research_partner.market_sources import collect_market, MARKET_OPERATIONS
from pydantic import ValidationError
from .research_partner.errors import Conflict as CoreConflict, InvalidRequest, NotFound, Unauthorized


def fields(body, required):
    if not isinstance(body, dict) or set(body) != set(required):
        raise Invalid("unexpected or missing fields")
    return body


class Service(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, config, researcher=snapshot):
        if config.get("host") != "127.0.0.1":
            raise Invalid("only loopback instances are supported")
        self.config = config
        # 先取得本实例端口；重复启动不得迁移数据库或中断现有任务。
        super().__init__((config["host"], config["port"]), Handler)
        try:
            self.repo = Repository(Path(config["database"]))
            self.mandates = Mandates(self.repo, config.get("instance_id", config["principal"]))
            self.repo.recover(abandoned=True)
            self.investment = Investment(self.mandates.store)
            self.strategies = Strategies(self.mandates.store)
            self.research_tools = ResearchToolBridge(self.repo, self.mandates.entities, strategies=self.strategies)
            self.researcher = researcher
            self.strategies.recovery()
            install_runtime(self)
        except BaseException:
            self.server_close()
            if getattr(self, "mandates", None) is not None:
                self.mandates.store.close()
            raise



class Handler(BaseHTTPRequestHandler):
    server: Service
    server_version = "Huohuo/1.0.0"

    def log_message(self, *_):
        pass  # 不向日志写入 URL、凭据或研究内容。

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def finish(self):
        try:
            super().finish()
        finally:
            # ThreadingHTTPServer 的请求线程结束后不会复用；不能一直保留其 SQLite 连接。
            self.server.mandates.store.close_current_connection()

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def do_OPTIONS(self):
        self.reply(403, {"error": "browser_origin_not_allowed"})

    def reply(self, status, body):
        encoded = canonical(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def authorized(self, role):
        expected = "Bearer " + self.server.config[role + "_token"]
        if not secrets.compare_digest(self.headers.get("Authorization", ""), expected):
            raise PermissionError("invalid credentials")

    def body(self, max_size=100_000):
        if self.headers.get("Transfer-Encoding"):
            raise Invalid("transfer encoding not supported")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise Invalid("invalid content length") from None
        if size < 2 or size > max_size:
            raise Invalid("body size outside bounds")
        if self.headers.get_content_type() != "application/json":
            raise Invalid("expected application/json")
        try:
            return json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError):
            raise Invalid("invalid json") from None

    def handle_request(self):
        try:
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != host or self.headers.get("Origin"):
                raise PermissionError("untrusted request origin")
            parsed = urlsplit(self.path)
            if parsed.query or parsed.scheme or parsed.netloc:
                raise Invalid("invalid request path")
            parts = parsed.path.strip("/").split("/")
            config, repo = self.server.config, self.server.repo
            if runtime_http(self, parts): return
            if parts[0] == "strategies":
                self.authorized("user")
                return strategy_http(self, parts)
            elif parts[0] == "investment":
                self.authorized("user")
                inv, principal = self.server.investment, config["principal"]
                if self.command == "GET" and parts == ["investment","account"]: return self.reply(200,inv.account(principal,self.server.market))
                if self.command == "GET" and parts == ["investment"]: return self.reply(200, inv.read(principal))
                if self.command == "GET" and len(parts)==3 and parts[1]=="previews": return self.reply(200,inv.inspect_preview(principal,parts[2]))
                if self.command == "POST":
                    body=self.body()
                    if parts == ["investment","bind-collection"]: return self.reply(200,self.server.mandates.investment_binding.bind(principal,body))
                    if parts == ["investment","preview"]: return self.reply(200,inv.preview(principal,body))
                    if parts == ["investment","risk-parse"]: return self.reply(200,inv.parse_risk(body))
                    if parts == ["investment","commit"]: return self.reply(200,inv.commit(principal,body))
                    if parts == ["investment","snapshot"]:
                        fields(body,("version",)); return self.reply(200,inv.snapshot(principal,body["version"]))
                    if parts == ["investment","collection"]:
                        fields(body,("collection","version")); return self.reply(200,CollectionProvider(inv,principal).read_snapshot(body["collection"],body["version"]))
            elif parts == ["research-tools", "run"] and self.command == "POST":
                self.authorized("user")
                body=fields(self.body(), ("session_id","call_id","tool_id","arguments"))
                return self.reply(200,self.server.research_tools.run(config["principal"],body["session_id"],body["call_id"],body["tool_id"],body["arguments"]))
            elif parts == ["research-tools", "evidence"] and self.command == "POST":
                self.authorized("user")
                body=fields(self.body(), ("session_id","evidence_id"))
                return self.reply(200,self.server.research_tools.evidence(config["principal"],body["session_id"],body["evidence_id"]))
            elif parts == ["entities", "search"] and self.command == "POST":
                self.authorized("user")
                body=fields(self.body(), ("query",))
                return self.reply(200, search_securities(body["query"]))
            elif parts == ["entities", "resolve"] and self.command == "POST":
                self.authorized("user")
                body=self.body()
                fields(body, ("query","session_id","mention_texts") if "mention_texts" in body else ("query","session_id"))
                return self.reply(200, self.server.mandates.entities.resolve(config["principal"],body["session_id"],body["query"],body.get("mention_texts")))
            elif parts == ["entities", "snapshot"] and self.command == "POST":
                self.authorized("user")
                body=fields(self.body(), ("session_id","snapshot_id","version"))
                return self.reply(200, self.server.mandates.entities.snapshot(config["principal"],body["session_id"],body["snapshot_id"],body["version"]))
            elif parts == ["entities", "confirm"] and self.command == "POST":
                self.authorized("user")
                body=fields(self.body(), ("session_id","snapshot_id","version","choices","source_call"))
                return self.reply(200, self.server.mandates.entities.confirm(config["principal"],body["session_id"],body["snapshot_id"],body["version"],body["choices"],body["source_call"]))
            elif parts[0] == "notifications":
                self.authorized("user")
                service=self.server.mandates.notifications
                if parts==["notifications","config"]:
                    if self.command=="GET":return self.reply(200,service.config(config["principal"]))
                    if self.command=="POST":return self.reply(200,service.save(config["principal"],self.body()))
                if parts==["notifications"] and self.command=="GET":return self.reply(200,service.list(config["principal"]))
            elif parts[0] == "mandates":
                self.authorized("user")
                core, principal = self.server.mandates, config["principal"]
                if self.command == "GET":
                    if parts == ["mandates"]: return self.reply(200, core.list(principal))
                    if len(parts) == 2: return self.reply(200, core.get(principal, parts[1]))
                if self.command == "POST":
                    body=self.body()
                    if parts == ["mandates"]: return self.reply(201, core.create(principal, body))
                    if len(parts)==3: return self.reply(200, core.command(principal,parts[1],parts[2],body))
            elif parts[0] == "executions" or parts == ["health"]:
                self.authorized("user")
                principal = config["principal"]
                if self.command == "GET":
                    if parts == ["executions"]:
                        return self.reply(200, repo.recent(principal))
                    if parts == ["health"]:
                        return self.reply(200, {"status": "ok", "version": "1.0.0", "schema": 1})
                    if len(parts) == 2:
                        return self.reply(200, repo.get(principal, parts[1]))
                    if len(parts) == 3 and parts[2] in ("events", "evidence"):
                        fn = repo.history if parts[2] == "events" else repo.evidence
                        return self.reply(200, fn(principal, parts[1]))
                if self.command == "POST":
                    body = self.body()
                    if parts == ["executions"]:
                        fields(body, ("request_key", "scope", "question"))
                        return self.reply(201, repo.request_research(principal, body["request_key"], body["scope"], body["question"]))
                    if len(parts) == 3 and parts[2] in ("cancel", "retry"):
                        fields(body, ("request_key", "expected_revision"))
                        return self.reply(200, repo.command(principal, parts[1], parts[2], body["request_key"], body["expected_revision"]))
            elif parts[0] == "worker":
                self.authorized("worker")
                if self.command == "POST":
                    body = self.body()
                    if parts == ["worker", "discover"]:
                        fields(body, ())
                        try:
                            self.server.calendar.refresh()
                            calendar_state = 'available'
                        except Exception:
                            calendar_state = 'unavailable'
                        return self.reply(200,dict(self.server.mandates.sources.discover(), calendar=calendar_state))
                    if parts == ["worker", "claim"]:
                        from .research_partner.model_admission import POLICY
                        fields(body, ("worker_id", "admission_policy", "lane") if 'lane' in body else ("worker_id", "admission_policy"))
                        if body['admission_policy'] != POLICY:
                            raise Invalid('worker 模型准入协议不兼容；请成组更新 worker 与侧车')
                        lane=body.get('lane','research')
                        if lane == 'strategy':
                            return self.reply(200,self.server.strategies.tasks.claim(config['principal'],body['worker_id']))
                        if lane != 'research': raise Invalid('未知执行资源类型')
                        self.server.mandates.tick()
                        job=repo.claim(body["worker_id"])
                        if job:
                            bound=self.server.mandates.store._connect().execute('SELECT mandate_id FROM execution_jobs WHERE execution_id=?',(job['execution_id'],)).fetchone()
                            if bound and self.server.mandates.position_risk.bindings.for_mandate(bound[0]):job['position_rule']=True
                            elif bound:
                                from .research_partner.price_execution import binding
                                if binding(self.server.mandates,job['execution_id'],config['principal']):job['price_rule']=True
                            row=self.server.mandates.store._connect().execute('SELECT * FROM investment_run_facts WHERE execution_id=?',(job['execution_id'],)).fetchone()
                            if row:job['investment_facts']={**self.server.investment.snapshot(row['principal'],row['version']),'collection':row['collection'],'mode':row['mode'],'members':json.loads(row['members'])}
                        return self.reply(200, job)
                    if parts == ["worker", "recover"]:
                        fields(body, ())
                        return self.reply(200, {"interrupted": repo.recover()})
                    if len(parts) == 4 and parts[1] == "attempts":
                        attempt, token = parts[2], self.headers.get("X-Attempt-Token", "")
                        if parts[3] == 'model-admission':
                            fields(body, ('phase',))
                            from .research_partner.model_admission import admit
                            return self.reply(200, admit(self.server, attempt, token, body['phase']))
                        if parts[3] == 'program-run':
                            fields(body, ())
                            from .research_partner.model_admission import run_program
                            return self.reply(200, run_program(self.server, attempt, token))
                        if parts[3]=='position-run':
                            fields(body,())
                            from .position_risk.execution import run
                            return self.reply(200,run(self.server,attempt,token))
                        if parts[3]=='price-run':
                            fields(body,())
                            from .research_partner.price_execution import run
                            return self.reply(200,run(self.server,attempt,token))
                        if parts[3] in ('strategy-run','strategy-result'):
                            with repo.connection() as db:
                                _,stored=repo._attempt(db,attempt,token)
                                if stored['principal']!=config['principal']: raise PermissionError('wrong owner')
                                row=repo._view(stored)
                            if row['scope'].get('kind')!='strategy': raise Invalid('不是策略执行')
                            jid=row['scope']['job_id']; strategies=self.server.strategies
                            if parts[3]=='strategy-run':
                                fields(body,())
                                from .strategies.background import run
                                return self.reply(200,run(strategies,config['principal'],jid,token))
                            return self.reply(200,strategies.planner_finish(config['principal'],jid,token,body))
                        if parts[3] == "heartbeat":
                            fields(body, ())
                            row=repo.active(attempt,token)
                            if row['scope'].get('kind')=='strategy':
                                return self.reply(200,self.server.strategies.tasks.heartbeat(config['principal'],row['scope']['job_id'],token))
                            return self.reply(200, repo.heartbeat(attempt, token))
                        if parts[3] == "runtime":
                            return self.reply(200, repo.runtime_receipt(attempt, token, body))
                        if parts[3] == "finish":
                            return self.reply(200, repo.finish(attempt, token, body))
            elif len(parts) == 3 and parts[0] == "attempts" and parts[2] == "research" and self.command == "POST":
                # 此能力仅可读取本次执行绑定的对象；不持有 user/worker 凭据。
                auth = self.headers.get("Authorization", "")
                token = auth[7:] if auth.startswith("Bearer ") else ""
                job = repo.active(parts[1], token)
                fields(self.body(), ())
                document = self.server.mandates.bound_source(job["execution_id"])
                if document is None:
                    scope = job["scope"]
                    document = collect_market(scope, self.server.market, self.server.calendar) if scope["operation"] in MARKET_OPERATIONS else self.server.researcher(scope) if scope["operation"] == "quote_snapshot" else collect(scope)
                # 采集在事务外执行；取消或租约过期后再次检查，禁止迟到写入。
                result = repo.save_evidence(parts[1], token, document)
                return self.reply(200, {"execution_id": job["execution_id"], **result})
            raise Missing("endpoint not found")
        except (PermissionError, Unauthorized):
            self.reply(403, {"error": "forbidden"})
        except (Invalid, InvalidRequest, ValidationError) as exc:
            self.reply(400, {"error": "invalid_request", "detail": str(exc)})
        except (Conflict, CoreConflict) as exc:
            self.reply(409, {"error": "conflict", "detail": str(exc)})
        except (Missing, NotFound):
            self.reply(404, {"error": "not_found"})
        except Exception:
            self.reply(500, {"error": "internal_error"})


def _parent_pipe_closed(kernel32, wintypes, handle):
    """Windows：非阻塞判断父进程管道的写端是否全部关闭。

    不能在后台线程里阻塞读 stdin：在 Windows 上它与请求线程中的大型 C 扩展
    导入（numpy/pandas 等）会互相卡死，实例随即停止接受连接，所有研究工具
    调用都变成“结果未确认”。stdin 不是管道（控制台/文件）时返回 False，
    让进程依赖 SIGTERM 正常退出，而不是自行关停。
    """
    import ctypes

    if kernel32.GetFileType(handle) != 3:  # FILE_TYPE_PIPE
        return False
    available = wintypes.DWORD()
    if kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
        return False
    return ctypes.get_last_error() == 109  # ERROR_BROKEN_PIPE


def parent_lifetime(shutdown):
    if sys.platform != 'win32':
        try:
            sys.stdin.buffer.read()
        except OSError:
            pass
        shutdown()
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    try:
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(sys.stdin.fileno()))
    except (OSError, ValueError):
        return
    while not _parent_pipe_closed(kernel32, wintypes, handle):
        time.sleep(1)
    shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--parent-pipe", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    with Service(config) as service:
        if args.parent_pipe:
            threading.Thread(target=parent_lifetime, args=(service.shutdown,), daemon=True).start()
        print(canonical({"event": "listening", "port": service.server_port}), flush=True)
        service.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
