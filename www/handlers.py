"""
URL handlers
"""

from www.coroweb import get
from www.models import User


@get('/')
async def index(request):
    # 从数据库中查询所有用户
    users = await User.findAll()
    return {
        '__template__': 'test.html',  # 指定使用名为 test.html 的模版
        'users': users  # 模版所需的参数
    }
