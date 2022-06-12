"""
定义了装饰器和 RequestHandler。
    1. 装饰器用于使处理函数带上要处理的URL信息（方法与路径），即完成URL到函数到映射；
    2. RequestHandler 包装处理函数，提供自动解析参数、以协程方式调用处理函数功能。
提供了URL处理函数的注册方法：add_route，add_routes，add_static.
"""
import asyncio
import functools
import logging


from aiohttp import web
from aiohttp.web_request import Request
from urllib import parse
from pathlib import Path

from www.apis import APIError

from www.coroweb_helper import *


def get(path):
    """
    定义装饰器 @get('/path')
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper

    return decorator


def post(path):
    """
    Define decorator @post('/path')
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper

    return decorator


class RequestHandler(object):
    """
    从URL函数中分析其需要接收的参数，从request中获取必要的参数，调用URL函数，然后把结果转换为web.Response对象
    """

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        # fn 最后一个参数的名字是否为 request
        self._has_request_arg = has_request_arg(fn)
        # fn 是否包含参数 **args（不定长字典）
        self._has_var_kw_arg = has_var_kw_arg(fn)
        # fn 是否包含必须用 'keyword=value' 的形式传参的有名参数（keyword-only 参数）
        self._has_named_kw_args = has_named_kw_args(fn)
        # 获取 fn 的 keyword-only 参数
        self._named_kw_args = get_named_kw_args(fn)
        # 获取 fn 的无默认值的 keyword-only 参数
        self._required_kw_args = get_required_kw_args(fn)

    async def __call__(self, request: Request):  # 使得实例可以视为函数一样调用
        # 步骤 1：获取参数
        kw = None
        # 先尝试从 request body 或 query string 中获取键值对参数（如 **args 或 keyword-only）
        if self._has_var_kw_arg or self._has_named_kw_args:
            if request.method == 'POST':
                # 参数位置 1：request body（POST 方法）
                if not request.content_type:
                    return web.HTTPBadRequest("Missing Content-Type")
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)

            if request.method == 'GET':
                # 参数位置 2： query string（GET 方法），如 /api/resource?p1=v1&p2=v2 问号后的部分
                qs = request.query_string
                if qs:
                    kw = {k: v[0] for k, v in parse.parse_qs(qs, True).items()}

        if kw is None:
            # 参数位置 3：URL 路径，如 @routes.get('/books/{book_id}') 的 book_id
            # 路由匹配以 {name:pattern} 形式捕获 URL 参数，可在 request.match_info 字典中获取
            # 参数作为 URL path 的一部分，如
            # https://stackoverflow.com/questions/51603030/how-to-get-dynamic-path-params-from-route-in-aiohttp-when-mocking-the-request
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # 若 _func 没有 **args，只有 keyword-only 参数，则 kw 只保留 keyword-only 参数
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy

            # 检查路由匹配参数和request body 的参数是否重复
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v

        if self._has_request_arg:
            kw['request'] = request

        # 检查是否包含必须的参数（不带默认值的）
        for name in self._required_kw_args:
            if name not in kw:
                return web.HTTPBadRequest('Missing argument: %s' % name)

        # 步骤 2：调用真正的处理函数，并返回结果
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


def add_route(app, fn):
    # fn 是否使用装饰器绑定了方法和路径
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    # 是否是协程
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    # 绑定处理函数
    logging.info(
        'add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))


def add_routes(app, module_name):
    """
    自动扫描指定模块下所有复合条件的函数，完成注册
    """
    # 引入模块
    n = module_name.rfind('.')  # 最右边的'.'的下标
    if n == -1:
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n + 1:]
        tmp = __import__(module_name[:n], globals(), locals(), [name])
        mod = getattr(tmp, name)
    # 读取模块中的处理函数
    for attr in dir(mod):  # dir 返回字符串列表
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            # 提前根据装饰器信息来判断该 fn 是否可能是处理函数，而不是通过 add_route 是否抛出异常来判断（费时）
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)


def add_static(app):
    """
    添加用于返回静态文件的路由器和处理程序。
    用于提供静态内容，如图像、javascript 和 css 文件
    """
    path = Path(__file__).resolve().parent / 'static'
    app.router.add_static('/static/', path)
