import json
from pathlib import Path
from aiohttp import web
from .data import DataMesher


def run(dm: DataMesher, port: int = 7331) -> None:
    routes = web.RouteTableDef()

    @routes.get('/')
    async def hello(request):
        return web.Response(text=json.dumps(dm.__json__()))

    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, port=port)
