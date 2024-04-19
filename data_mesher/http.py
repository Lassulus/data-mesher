from aiohttp import web

from .data import DataMesher


def run(dm: DataMesher, port: int = 7331) -> None:
    routes = web.RouteTableDef()

    @routes.get("/")
    async def get_data(request: web.Request) -> web.Response:
        return web.json_response(dm.__json__())

    @routes.post("/")
    async def post_data(request: web.Request) -> web.Response:
        data = await request.post()
        other = DataMesher(networks=data)
        dm.merge(other)
        return web.json_response(dm.__json__())

    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, port=port)
