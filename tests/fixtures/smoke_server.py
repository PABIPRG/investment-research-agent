"""仅由冒烟夹具启动，复用真实 API/Repository/计算；不安装到产品服务入口。"""
import json
import sys
import threading
import time
from pathlib import Path

from huohuo.server import Service
from huohuo.research import snapshot
from huohuo.execution import Conflict


instance = Path(sys.argv[1]).resolve()
owner = json.loads((instance.parent / "smoke-owner.json").read_text())
assert owner["instance"] == str(instance), "not an owned smoke instance"
config = json.loads((instance / "instance.json").read_text())
control = instance / "fixture.json"


def fixture(scope):
    mode = json.loads(control.read_text())["mode"]
    if mode == "hold":
        (instance / "tool-entered").write_text("entered")
        deadline = time.monotonic() + 10
        while not (instance / "tool-release").exists():
            if time.monotonic() > deadline:
                raise TimeoutError("smoke gate timed out")
            time.sleep(0.02)
    def loader(_):
        if mode == "error":
            raise TimeoutError("synthetic provider failure")
        return ({"rc": 0, "data": {"diff": [{"f12": scope["entity_id"].split(":")[-1], "f14": "合成冒烟样本",
                  "f2": 12.1, "f18": 10, "f124": 1792569600}]}}, "https://example.invalid/huohuo-smoke-fixture")
    return snapshot(scope, loader)


with Service(config, researcher=fixture) as service:
    original = service.repo.save_evidence
    def observe_save(attempt_id, token, document):
        outcome = "unexpected_error"
        reason = None
        try:
            result = original(attempt_id, token, document)
            outcome = "stored"
            return result
        except Conflict as error:
            outcome = "rejected"
            reason = str(error)
            raise
        except Exception as error:
            reason = type(error).__name__
            raise
        finally:
            with (instance / "evidence-outcomes.jsonl").open("a") as stream:
                stream.write(json.dumps({"attempt_id": attempt_id, "outcome": outcome, "reason": reason}) + "\n")
    service.repo.save_evidence = observe_save
    def parent_lifetime():
        sys.stdin.buffer.read()
        service.shutdown()
    threading.Thread(target=parent_lifetime, daemon=True).start()
    print(json.dumps({"event": "listening", "port": service.server_port, "pid": __import__("os").getpid()}), flush=True)
    service.serve_forever(poll_interval=0.1)
