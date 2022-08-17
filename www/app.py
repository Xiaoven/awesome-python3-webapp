"""
程序入口
主要包括jinja2初始化、middlewares和应用初始化等函数
- jinja2 用于根据定义好的 HTML 模版中的变量和指令，生成最终返回的 HTML 文本
- middleware 是拦截器，在handler执行前后进行一些通用操作
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

from www import orm
from www.coroweb import add_routes, add_static
from www.config import configs
from handlers import _cookie2user, COOKIE_NAME

logging.basicConfig(level=logging.DEBUG)


###############
#  jinja2 相关 #
###############
def init_jinja2(**kw):
    logging.info('init jinja2...')

    # 模版存放路径
    path = kw.get('path', None)
    if path is None:
        path = Path(__file__).resolve().parent / 'templates'
    logging.info('set jinja2 template path: %s' % path)

    # jinja2 环境配置参数
    options = dict(
        autoescape=kw.get('autoescape', True),  # 是否启用 XML/HTML 自动转义功能
        auto_reload=kw.get('auto_reload', True),  # 每次请求模版时，检查模版是否有更新
        # 指令语法标记
        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%}'),
        # 变量替换语法标记
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
    )

    # 初始化 jinja2 的核心组件
    env = Environment(loader=FileSystemLoader(path), **options)

    # filters 是一个 python 函数字典，见 https://jinja.palletsprojects.com/en/3.1.x/api/#writing-filters
    # 在模版中的用法例子： {{ 42|myfilter(23) }}，代表方法调用 myfilter(42, 23)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f

    return env


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


###############
#   拦截函数   #
###############
"""
https://docs.aiohttp.org/en/stable/web_advanced.html#aiohttp-web-middlewares
Middleware:
    - a coroutine that can modify either the request or response.
    - aiohttp.web.middleware 装饰器：
        Every middleware should accept two parameters, a request instance and a handler, and return the response or raise
an exception.
        Note: Second argument should be named handler exactly.

Middleware factory:
    - a function that creates a middleware with passed arguments. 
"""


@web.middleware
async def logger(request, handler):
    """
    调用handler之前，先打 log
    """
    logging.info('Request: %s %s' % (request.method, request.path))
    return await handler(request)

@web.middleware
async def auth(request, handler):
    """在调用handler前解析cookie，以检查登陆状态"""
    logging.info('check user: %s %s' % (request.method, request.path))
    request.__user__ = None
    cookie_str = request.cookies.get(COOKIE_NAME)
    if cookie_str:
        user = await _cookie2user(cookie_str)
        if user:
            logging.info('set current user: %s' % user.email)
            request.__user__ = user
    if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
        return web.HTTPFound('/signin')
    return await handler(request)

# @web.middleware
# async def parse_data(request, handler):
#     """
#     调用handler之前，提前获取数据并存为 __data__ 属性
#     """
#     if request.method == 'POST':
#         if request.content_type.startswith('application/json'):
#             request.__data__ = await request.json()
#             logging.info('request json: %s' % str(request.__data__))
#         elif request.content_type.startswith('application/x-www-form-urlencoded'):
#             request.__data__ = await request.post()
#             logging.info('request form: %s' % str(request.__data__))
#     return await handler(request)


def response_factory(env):
    """
    通过闭包的方式将 env 注入 response 处理方法，并返回该闭包
    :param env: jinja2 的核心组件 env
    """

    @web.middleware
    async def response(request, handler):
        """
        调用handler来处理request，拿到response，并进行处理
        """
        logging.info('Response handler...')
        logging.debug(f'handler info: {handler.__name__}')
        r = await handler(request)
        logging.debug(f'[Result type] {type(r)}\n' + str(r))
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'  # 响应类型是HTML文本，并且编码是UTF-8
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')  # 要使用的模版名
            if template is None:  # 可能是自定义的异常信息
                resp = web.Response(
                    body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                # 访问 jinja2 的核心组件 env，用来获取html模版
                r['__user__'] = request.__user__  # 统一注入用户信息
                resp = web.Response(body=env.get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and 100 <= r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and 100 <= t < 600:
                return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp

    return response


############
# 应用初始化 #
############
async def init():
    # 创建全局数据库连接池
    await orm.create_pool(host=configs.db.host, port=configs.db.port, user=configs.db.user,
                          password=configs.db.password, db=configs.db.db)
    # 初始化 jinja2
    env = init_jinja2(filters=dict(datetime=datetime_filter))
    # 创建 aiohttp 服务器
    app = web.Application(middlewares=[logger, auth, response_factory(env)])
    # 批量注册handlers模块下的处理方法
    add_routes(app, 'handlers')
    # 注册静态资源默认的存储位置
    add_static(app)
    return app


if __name__ == '__main__':
    app = init()
    web.run_app(app, host='127.0.0.1', port='9000')
