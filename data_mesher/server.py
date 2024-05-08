import asyncio
import ipaddress
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

from aiohttp import web
from nacl.signing import SigningKey

from .app_keys import BOOTSTRAP_PEERS, CLIENT, DATA
from .client import create_client
from .data import DataMesher

log = logging.getLogger(__name__)


@dataclass
class ServerSettings:
    bootstrap_peers: list[str]
    port: int
    key: SigningKey
    state_file: Path
    ip: ipaddress.IPv6Address


def create_routes(app: web.Application) -> web.Application:
    routes = web.RouteTableDef()

    @routes.get("/")
    async def get_data(request: web.Request) -> web.Response:
        dm = app[DATA]
        return web.json_response(dm.__json__())

    @routes.post("/")
    async def post_data(request: web.Request) -> web.Response:
        data = await request.post()
        other = DataMesher(networks=dict(data))
        dm = app[DATA]
        dm.merge(other)
        return web.json_response(dm.__json__())

    app.add_routes(routes)
    return app


async def background_tasks(app: web.Application) -> AsyncGenerator[None, None]:
    app[CLIENT] = asyncio.create_task(create_client(app))

    yield

    app[CLIENT].cancel()


def spawn_server(
    data_mesher: DataMesher, bootstrap_peers: list[str] = []
) -> web.Application:
    log.info("Starting server")
    app = web.Application()
    app[BOOTSTRAP_PEERS] = bootstrap_peers
    app[DATA] = data_mesher

    app.cleanup_ctx.append(background_tasks)
    create_routes(app)

    return app
