import logging

import aiomysql


def log(sql):
    logging.info('SQL: %s' % sql)


async def create_pool(loop, **kw):
    logging.info('create database connection pool...')

    global _pool  # 想对全局变量 _pool 赋值，需要先声明该函数里的 _pool 是全局变量
    _pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw.get('password'),
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )


async def select(sql, args, size=None):
    log(sql)

    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # SQL 与 MySQL 占位符不同
            # 使用带参数的 SQL 而不是自己拼接，可以防止SQL注入攻击
            await cur.execute(sql.replace('?', '%s'), args or ())
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        logging.info('rows returned: %s' % len(rs))
        return rs


async def execute(sql, args, autocommit=True):
    """
    执行INSERT、UPDATE、DELETE语句，返回一个整数表示影响的行数
    """
    log(sql)

    async with _pool.acquire() as conn:
        if not autocommit:
            # 不想使用autocommit，需要开启事务transaction，保证操作要么全部执行，要么都不执行
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()  # 不 autocommit，就要显式调用该方法，将修改写入数据库
        except Exception as e:
            if not autocommit:
                await conn.rollback()  # commit 出错需要执行回滚
            raise
        return affected


############
# ORM 模型 #
###########


class Field:
    def __init__(self, name, column_type, primary_key, default):
        """
        保存数据库表的字段名和字段类型等信息
        :param name: 列名
        :param column_type: 数据类型
        :param primary_key: 是否为主键
        :param default: 默认值
        """
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):
    def __init__(self, name, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


def _create_args_string(num):
    L = ['?' for _ in range(num)]
    return ', '.join(L)


class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        # 排除Model类本身，只处理用户自定义的类（Model的子类）
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)

        # 获取table名称，如果没有指定表名，则用类名作为表名
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))

        # 获取所有的Field和主键名
        mappings, fields, primaryKey = dict(), list(), None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v

                # 检查当前列是主键还是普通 field，一个表格只能有一个主键
                if v.primary_key:
                    if primaryKey:
                        raise Exception('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)

        if not primaryKey:
            raise Exception('Primary key not found.')

        # 将列字段从attrs移除，它们将存在 mappings 等属性下
        for k in mappings.keys():
            attrs.pop(k)

        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        escaped_fields_str = ', '.join(escaped_fields)
        # 列名不一定跟 field 名字相同，如果没有指定列名，才使用 field 名作为列名
        update_str = ', '.join(map(lambda f: f'`{mappings.get(f).name or f}`=?', fields))

        attrs['__mappings__'] = mappings  # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey  # 主键属性名
        attrs['__fields__'] = fields  # 除主键外的属性名
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句，后面的数据库操作方法根据这里的定义准备数据
        # 把列名和等待填充的参数（用"?"占位）加进语句里
        attrs['__select__'] = f'select `{primaryKey}`, {escaped_fields_str} from `{tableName}`'
        attrs[
            '__insert__'] = f'insert into `{tableName}` ({escaped_fields_str}, `{primaryKey}`) values ({_create_args_string(len(escaped_fields))})'
        attrs['__update__'] = f'update `{tableName}` set {update_str} where `{primaryKey}`=?'
        attrs['__delete__'] = f'delete from `{tableName}` where `{primaryKey}`=?'

        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):  # 继承 dict，支持字典的读写语法
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    # 实现特殊方法 __getattr__()和__setattr__()，使其支持通过 "." 引用字段或新增字段
    def __getattr__(self, key):
        return self[key]  # 失败会抛出 AttributeError

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        """
        仅在实例对象包含的attributes中找
        """
        return getattr(self, key, None)  # 相当于带默认值的 self.key

    def getValueOrDefault(self, key):
        """
        可自动为实例补全缺少的列属性（可能这部分数据没那么重要）
        1. 查找类的实例对象是否包含key
        2. 如果不包含，但 __mappings__（表格定义）又包含了 key 对应的列，就取默认值，并添加到实例对象的attributes中
        """
        value = getattr(self, key, None)
        # 如果 self 下找不到，就去 cls 的 __mappings__ 下面找
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:  # 如果该列的默认值不为 None，则返回默认值
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    # 数据库方法
    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        """
        find objects by where clause.
        """
        sql = [cls.__select__]

        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []

        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)

        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))

        rs = await select(' '.join(sql), args)

        # **r 将字典 r 拆解，作为变量传给函数
        # cls() 相当于调用了当前类的构造函数
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        """ find object by primary key. """
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    async def save(self):
        """
        将当前实例的数据作为行插入表格
        需要按表格定义的列（__mappings__）准备数据，如果实例不包含某列，则取默认值
        """
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primaryKey__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warning('failed to insert record: affected rows: %s' % rows)

    async def update(self):
        """
        需要更新的数据一定出现在实例的attributes（已经经过save补全了列数据，或是从数据库读反序列化得到的）
        所以用 self.getValue 而不是 self.getValueOrDefault
        """
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primaryKey__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warning('failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primaryKey__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warning('failed to remove by primary key: affected rows: %s' % rows)
