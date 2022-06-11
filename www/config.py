"""
优先从 config_override.py 中读取配置，并于 config_default.py 的合并
"""
from www import config_default


class Dict(dict):
    """
    Simple dict but support access as x.y style.
    """

    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v

    # 以下两个特殊方法使得该字典子类可以通过 x.y 风格访问键值对
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


def merge(defaults, override):
    r = dict()
    for k, v in defaults.items():
        if k in override:
            # 优先使用 override 的值，如果 v 是字典，则进行递归
            r[k] = merge(v, override[k]) if isinstance(v, dict) else override[k]
        else:
            # 使用 default 的值
            r[k] = v
    return r


def toDict(d):
    D = Dict()
    for k, v in d.items():
        # 如果 v 是字典，需要进行递归
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D


configs = config_default.configs

try:
    import config_override  # 不一定存在
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

configs = toDict(configs)
