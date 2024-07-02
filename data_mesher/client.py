import asyncio
import logging

from aiohttp import ClientSession, client_exceptions, web

from .app_keys import BOOTSTRAP_PEERS, DATA
from .data import DataMesher, load

log = logging.getLogger(__name__)


async def create_client(app: web.Application) -> None:
    log.debug("create_client")
    dm = app[DATA]
    bootstrap_peers: list[str] = app[BOOTSTRAP_PEERS]
    log.debug(app)
    async with ClientSession() as session:
        while True:
            log.debug(f"bootstrap_peers: {bootstrap_peers}")
            if bootstrap_peers:
                for hostname in bootstrap_peers:
                    try:
                        log.debug(f"connecting to bootstrap peer: {hostname}")
                        async with session.get(
                            hostname, json=dm.__json__()
                        ) as response:
                            data = await response.json()
                            log.debug(f"[client] received {data}")
                            other = DataMesher(networks=load(data))
                            log.debug(f"[client] other data parsed: {other.__json__()}")
                            dm.merge(other)
                            dm.save()
                            log.debug(f"[client] merged data: {dm.__json__()}")
                            log.debug(f"[client] DEBUG data: {dm.host}")
                        async with session.post(
                            hostname, json=dm.__json__()
                        ) as response:
                            data = await response.json()
                            log.debug(f"[client] received {data}")
                        # TODO add to not_seen_bootstrap_peers if timeout or error
                    except client_exceptions.InvalidURL as e:
                        log.debug(
                            f"[client] connection failed with invalid url: {hostname} error: {e}"
                        )
                    except client_exceptions.ClientConnectorError as e:
                        log.debug(
                            f"[client] connection failed with client connector error: {hostname} error: {e}"
                        )

            for host in dm.all_hosts:
                log.debug(f"[client] checking if ${host} is up2date")
                if not host.is_up2date():
                    log.debug(f"[client] ${host} is not up2date")
                    async with session.post(
                        f"http://[{host.ip}]:{host.port}", json=dm.__json__()
                    ) as response:
                        data = await response.json()
                        # log.debug(f"received {data}")
                        other = DataMesher(networks=data)
                        dm.merge(other)
                        dm.save()
            await asyncio.sleep(5)
