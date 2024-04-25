import time

from aiohttp import ClientSession, web, client_exceptions

from .data import DataMesher


async def server(app: web.Application) -> web.Application:
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


async def client(app: web.Application) -> None:
    dm = app["data"]
    async with ClientSession() as session:
        while True:
            print("busy client loop start")
            not_seen_bootstrap_peers: list[str] = []
            if "bootstrap_peers" in app:
                print(app["bootstrap_peers"])
                for host in app["bootstrap_peers"]:
                    print("connecting to bootstrap peer", host)
                    try:
                        async with session.post(host, json=dm.__json__()) as response:
                            other = DataMesher(networks=await response.json())
                            dm.merge(other)
                        # TODO add to not_seen_bootstrap_peers if timeout or error
                    except client_exceptions.InvalidURL:
                        pass
                    except client_exceptions.ClientConnectorError:
                        not_seen_bootstrap_peers.append(host)
            app["bootstrap_peers"] = not_seen_bootstrap_peers
            for host in dm.all_hosts:
                if not host.is_up2date():
                    async with session.post(host, json=dm.__json__()) as response:
                        other = DataMesher(networks=await response.json())
                        dm.merge(other)
            time.sleep(5)
