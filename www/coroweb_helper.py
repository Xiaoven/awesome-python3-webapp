import inspect


def get_required_kw_args(fn):
    """
    获取必须以 'keyword=value' 的形式传参（定义在 *args 或 * 之后） 且不带默认值的参数
    e.g. def foo(a, b, *, c, d=10) 中的 c
    """
    args = list()
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)


def get_named_kw_args(fn):
    """
    获取出现在 *args（或 *）之后的参数（必须以 'keyword=value' 的形式传参）
    e.g. def foo(a, b, *, c) 中的 c
    """
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


def has_named_kw_args(fn):
    """
    是否存在出现在 *args（或 *）之后的参数（必须以 'keyword=value' 的形式传参）
    e.g. def foo(a, b, *, c) 中的 c
    """
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True


def has_var_kw_arg(fn):
    """是否存在 **kwargs 参数 (VAR_KEYWORD，不定长的字典)"""
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True


def has_request_arg(fn):
    """
    检查方法是否包含名为 request 的参数，且该参数是最后一个命名参数
    """
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        # request 参数后没有 *args、**kw、出现在 *args（或 *） 之后的参数
        if found and (
                param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError(
                'request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found