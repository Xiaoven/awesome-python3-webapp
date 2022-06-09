import logging
import asyncio
from aiohttp import web

logging.basicConfig(level=logging.INFO)


async def index(request):
    return web.Response(text='Hello Aiohttp!')


def setup_routes(app):
    app.router.add_get('/', index)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    app = web.Application(loop=loop)
    setup_routes(app)
    web.run_app(app, host='127.0.0.1', port='9000')
