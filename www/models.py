import time
import uuid

from www.orm import Model, StringField, BooleanField, FloatField, TextField


def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)


class User(Model):
    """
    以下类属性均是描述表格的。
    由于父类 Model 设置了 metaclass，会通过 ModelMetaclass 的 __new__ 方法创建 User 类，
    即这些列属性会以 dict 的形式被移到一个名为 __mappings__ 的类属性下统一管理，
    也是为了避免被后面绑定的同名实例属性覆盖，因为实例属性的优先级高于类属性。

    实例属性可以在新建实例对象后，调用一次 save() 来自动初始化/绑定。
    """
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    # 日期/时间用float存储在数据库中，而非datetime，好处是不必关心数据库的时区以及时区转换问题，排序简单，显示时只需要做float到str的转换
    created_at = FloatField(default=time.time)


class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)


class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)
