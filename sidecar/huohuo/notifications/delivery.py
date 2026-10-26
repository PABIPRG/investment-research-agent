"""复用旧通知适配器的确定性/可重试性错误契约。"""
from typing import Protocol

class DeliveryAdapter(Protocol):
    def send(self, job: dict) -> None:
        """发送一条已领取的任务；失败时抛出 DeliveryError。"""


class DeliveryError(RuntimeError):
    """渠道适配器提供的可重试性和结果确定性。"""

    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        outcome_uncertain: bool,
        message: str | None = None,
    ):
        super().__init__(message or code)
        self.code = code
        self.retryable = retryable
        self.outcome_uncertain = outcome_uncertain


class DeliverySuppressed(RuntimeError):
    """渠道未配置、未授权或没有可用接收目标。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


