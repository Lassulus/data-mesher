from aiohttp import web

from .data import DataMesher


async def create_server(app: web.Application) -> web.Application:
    routes = web.RouteTableDef()

    @routes.get("/")
    async def get_data(request: web.Request) -> web.Response:
        dm = app["data"]
        return web.json_response(dm.__json__())

    @routes.post("/")
    async def post_data(request: web.Request) -> web.Response:
        data = await request.post()
        other = DataMesher(networks=dict(data))
        dm = app["data"]
        dm.merge(other)
        return web.json_response(dm.__json__())

    app.add_routes(routes)
    return app
