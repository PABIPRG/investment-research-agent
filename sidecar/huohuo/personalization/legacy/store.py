class JsonStore:
    def __init__(self,*args,**kwargs):
        raise RuntimeError('旧全局存储已禁用；必须传入当前主体的快照端口')
