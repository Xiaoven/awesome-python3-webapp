"""
URL handlers
"""
import time

from www.coroweb import get
from www.models import User, Blog


@get('/')
async def index(request):
    # 临时构建Blog对象，未涉及数据库操作
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
    ]
    return {
        '__template__': 'blogs.html',  # 指定模版
        'blogs': blogs  # 模版所需的参数
    }


# Web API, 返回 JSON 格式的数据
@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy='created_at desc')
    for u in users:
        u.password = '******'
    return dict(users=users)
