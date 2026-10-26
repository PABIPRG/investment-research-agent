"""旧窄算法所需的内存文档端口；持久化仅由 Investment 服务负责。"""
import copy
class Document:
    def __init__(self, value): self.value = copy.deepcopy(value)
    def all(self, collection): return copy.deepcopy(self.value)
    def get(self, collection, key, default=None): return copy.deepcopy(self.value.get(key, default))
    def mutate_document(self, collection, fn): self.value = fn(copy.deepcopy(self.value))
