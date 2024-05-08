from asyncio import Task

from aiohttp import web

from .data import DataMesher

CLIENT = web.AppKey("client", Task)
DATA = web.AppKey("data", DataMesher)
BOOTSTRAP_PEERS = web.AppKey("bootstrap_peers", list[str])
