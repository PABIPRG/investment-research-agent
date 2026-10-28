"""迁移后的统一查询仓库；旧算法按查询职责拆分。"""
from .repository_base import RepositoryBase
from .profiles import Profiles
from .relations import Relations
from .universe import Universe
from .network import Network


class GraphRepository(RepositoryBase, Profiles, Relations, Universe, Network):
    pass
