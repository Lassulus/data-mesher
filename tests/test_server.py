import asyncio
import ipaddress
import logging
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

import pytest
from aiohttp.test_utils import TestServer
from aiohttp.web import Application
from nacl.signing import SigningKey

from data_mesher.app_keys import DATA
from data_mesher.data import DataMesher, Host, Hostname, Network
from data_mesher.server import spawn_server

log = logging.getLogger(__name__)

AiohttpServer = Callable[[Application], Awaitable[TestServer]]


@pytest.fixture
def aiohttp_server(event_loop: asyncio.AbstractEventLoop) -> Iterator[AiohttpServer]:
    """Factory to create a TestServer instance, given an app.

    aiohttp_server(app, **kwargs)
    """
    servers = []

    async def go(app, *, port: int | None = None, host: str = "::1", **kwargs):  # type: ignore[no-untyped-def]
        server = TestServer(app, port=port, host=host)
        await server.start_server(**kwargs)
        servers.append(server)
        return server

    yield go

    async def finalize() -> None:
        while servers:
            await servers.pop().close()

    event_loop.run_until_complete(finalize())


@pytest.mark.asyncio
async def test_server(
    temporary_dir: Path,
    unused_tcp_port_factory: Callable[[], int],
    aiohttp_server: Callable,
) -> None:
    logging.basicConfig(level=logging.DEBUG)
    log.info("Starting test")

    state1 = temporary_dir / "state1.json"
    key1 = SigningKey.generate()
    s1_port = unused_tcp_port_factory()
    host1 = Host(
        ip=ipaddress.IPv6Address("::1"),
        port=s1_port,
        publicKey=key1.verify_key,
        hostnames={"s1": Hostname("s1")},
    )
    network1 = Network(
        tld="test",
        public=True,
        hostSigningKeys=[key1.verify_key],
        hosts={key1.verify_key: host1},
    )
    s1 = spawn_server(
        data_mesher=DataMesher(
            state_file=state1,
            networks={"test": network1},
        ),
    )
    print(f"listening on {s1_port}")
    await aiohttp_server(s1, port=s1_port, host="::1")
    state2 = temporary_dir / "state2.json"
    key2 = SigningKey.generate()
    s2_port = unused_tcp_port_factory()

    network2 = Network(
        tld="test",
    )
    s2 = spawn_server(
        data_mesher=DataMesher(
            host=Host(
                ip=ipaddress.IPv6Address("::1"),
                port=s2_port,
                publicKey=key2.verify_key,
                hostnames={"s2": Hostname("s2")},
            ),
            networks={"test": network2},
            state_file=state2,
        ),
        bootstrap_peers=[f"http://[::1]:{s1_port}"],
    )

    print(f"listening on {s2_port}")
    await aiohttp_server(s2, port=s2_port, host="::1")
    await asyncio.sleep(10)
    data_mesher: DataMesher = s2[DATA]
    log.info(data_mesher.networks["test"].__json__())
