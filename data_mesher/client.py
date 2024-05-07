import asyncio
import logging

from aiohttp import ClientSession, client_exceptions, web

from .data import DataMesher

log = logging.getLogger(__name__)


async def create_client(app: web.Application) -> None:
    dm = app["data"]
    async with ClientSession() as session:
        while True:
            not_seen_bootstrap_peers: list[str] = []
            if "bootstrap_peers" in app:
                log.debug(f"bootstrap_peers: {app['bootstrap_peers']}")
                for host in app["bootstrap_peers"]:
                    try:
                        log.debug(f"connecting to bootstrap peer: {host}")
                        async with session.post(host, json=dm.__json__()) as response:
                            data = await response.json()
                            log.debug(f"received {data}")
                            other = DataMesher(networks=data)
                            dm.merge(other)
                        # TODO add to not_seen_bootstrap_peers if timeout or error
                    except client_exceptions.InvalidURL as e:
                        log.debug(
                            f"connection failed with invalid url: {host} error: {e}"
                        )
                    except client_exceptions.ClientConnectorError as e:
                        log.debug(
                            f"connection failed with client connector error: {host} error: {e}"
                        )
                        not_seen_bootstrap_peers.append(host)

            app["bootstrap_peers"] = not_seen_bootstrap_peers
            for host in dm.all_hosts:
                log.debug(f"checking if ${host} is up2date")
                if not host.is_up2date():
                    async with session.post(host, json=dm.__json__()) as response:
                        data = await response.json()
                        #log.debug(f"received {data}")
                        other = DataMesher(networks=data)
                        dm.merge(other)
            await asyncio.sleep(5)
