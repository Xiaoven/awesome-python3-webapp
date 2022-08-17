"""
URL handlers
"""
import hashlib
import json
import logging
import re
import time

from aiohttp import web

from www.apis import APIValueError, APIError
from www.config import configs
from www.coroweb import get, post
from www.models import User, Blog, next_id

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret


@get('/')
def index(request):
    # 临时构建Blog对象，未涉及数据库操作
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 7200)
    ]
    return {
        '__template__': 'blogs.html',  # 指定模版
        'blogs': blogs # 模版所需的参数
    }


@get('/register')
def register():
    return {
        '__template__': 'register.html',
    }


@get('/signin')
def signin():
    return {
        '__template__': 'signin.html',
    }


@get('/signout')
def signout(request):
    """
    Referer 字段：访问来源信息，来源网站的 URL
    以下场景会发送该字段：
        1 - 点击网页上的链接
        2 - 发送表单
        3 - 加载静态资源（图片、脚本、样式）
    """
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')  # 状态码是 302
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r


_RE_EMAIL = re.compile(r'^[a-z0-9.\-_]+\@[a-z0-9\-_]+(\.[a-z0-9\-_]+){1,4}$');
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


@post('/api/users')
async def api_register_user(*, email, name, passwd):
    # 检查数据格式
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    # 查找邮箱是否已注册
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    # 将新用户信息存到数据库
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)  # passwd 在客户端那边已经加密过一次了，服务器这边基于它再加密一次
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # 生成会话 cookie
    return _authenticate_with_cookie(user)


@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')

    # check if user exists
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]  # 有规定一个邮箱只能注册一个账号

    # check passwd
    sha1 = hashlib.sha1()  # 创建一个 hash 对象
    sha1.update(user.id.encode('utf8'))  # feed the hash object with bytes-like objects
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():  # 获取迄今为止提供给它的数据的串联在一起后的摘要
        raise APIValueError('passwd', 'Invalid password.')

    # authenticate ok, set cookie
    return _authenticate_with_cookie(user)


#################
#  Help Methods #
#################
def _user2cookie(user, max_age):
    """
    Generate cookie str by user.
    """
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


async def _cookie2user(cookie_str):
    """Parse cookie and load user if cookie is valid"""
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) == 3:
            uid, expires, sha1 = L
            if int(expires) > time.time():
                user = await User.find(uid)
                if user:
                    s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
                    if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
                        logging.info('Invalid sha1')
                    else:
                        user.passwd = '******'
                        return user
    except Exception as e:
        logging.exception(e)
    return None


def _authenticate_with_cookie(user):
    r = web.Response()  # 状态码默认是 200
    # HttpOnly 是微软对 Cookie 做的扩展，该值指定 Cookie 是否可通过客户端脚本访问。将其设为 true 可以防止攻击者可以通过程序(JS脚本、Applet等)获取到用户的 Cookie 信息
    r.set_cookie(COOKIE_NAME, _user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
