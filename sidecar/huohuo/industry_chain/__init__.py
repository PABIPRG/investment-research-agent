"""嵌入本实例的产业链能力，不启动旧服务器或独立 Agent。"""
from .service import IndustryChainService
from .query import ROUTES

__all__ = ['IndustryChainService', 'ROUTES']
