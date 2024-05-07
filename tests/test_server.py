import asyncio
import ipaddress
import logging
from pathlib import Path
from collections.abc import Iterator
from aiohttp.test_utils import TestServer
from typing import Awaitable, Callable
from aiohttp.web import Application

import pytest
from nacl.signing import SigningKey

from data_mesher import ServerSettings, spawn_server
from data_mesher.data import DataMesher

log = logging.getLogger(__name__)

AiohttpServer = Callable[[Application], Awaitable[TestServer]]

@pytest.fixture
def aiohttp_server2(loop: asyncio.AbstractEventLoop) -> Iterator[AiohttpServer]:
    """Factory to create a TestServer instance, given an app.

    aiohttp_server(app, **kwargs)
    """
    servers = []

    async def go(app, *, port=None, host="::1", **kwargs):  # type: ignore[no-untyped-def]
        server = TestServer(app, port=port, host="::1")
        await server.start_server(**kwargs)
        servers.append(server)
        return server

    yield go

    async def finalize() -> None:
        while servers:
            await servers.pop().close()

    loop.run_until_complete(finalize())

@pytest.mark.asyncio
async def test_server(
    temporary_dir: Path,
    # unused_tcp_port_factory,
    aiohttp_server2,
) -> None:
    logging.basicConfig(
        level=logging.DEBUG
    )
    log.info("Starting test")
    state1 = temporary_dir / "state1.json"
    key1 = SigningKey.generate()
    s1_port = 123456
    s1 = spawn_server(
        ServerSettings(
            bootstrap_peers=[],
            ip=ipaddress.IPv6Address("::1"),
            port=s1_port,
            key=key1,
            state_file=state1,
        )
    )
    print(f"listening on {s1_port}")
    await aiohttp_server2(s1, port=s1_port, host="::1")
    state2 = temporary_dir / "state2.json"
    key2 = SigningKey.generate()
    s2_port = 123457

    s2 = spawn_server(
        ServerSettings(
            bootstrap_peers=[f"http://[::1]:{s1_port}"],
            ip=ipaddress.IPv6Address("::1"),
            port=s2_port,
            key=key2,
            state_file=state2,
        )
    )
    #await asyncio.sleep(3)
    #client = await aiohttp_client(s2)
    #res = await client.get("/")
    #breakpoint()

    print(f"listening on {s2_port}")
    await aiohttp_server2(s1, port=s2_port, host="::1")
    await asyncio.sleep(10)
    print(dir(s2))
    data_mesher : DataMesher = s2["data"]
    print(data_mesher.networks)
    print(s2["bootstrap_peers"])
