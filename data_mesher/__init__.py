import argparse
import asyncio
import ipaddress
import os
import socket
from collections.abc import AsyncGenerator
from pathlib import Path

from aiohttp import web
from nacl.encoding import Base64Encoder
from nacl.signing import SigningKey

from .data import DataMesher, Host
from .http import client, server


async def background_tasks(app: web.Application) -> AsyncGenerator[None, None]:
    app[client] = asyncio.create_task(client(app))

    yield

    app[client].cancel()
    await app[client]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["server", "create", "test"],
        default=None,
    )
    parser.add_argument(
        "--state-file",
        default="/tmp/data_mesher.json",
    )
    parser.add_argument(
        "--hostname",
        default=str(socket.gethostname()),
    )
    parser.add_argument(
        "--ip",
        required=True,
    )
    parser.add_argument(
        "--port",
        default=7331,
    )
    parser.add_argument(
        "--key-file",
        default=f"{os.environ['HOME']}/.config/data/data-mesher/key",
    )
    parser.add_argument(
        "--bootstrap-peer",
        action="append",
        default=[],
    )
    args = parser.parse_args()

    key_file = Path(args.key_file)
    if not key_file.exists():
        key = SigningKey.generate()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key.encode(Base64Encoder))
    else:
        key = SigningKey(key_file.read_bytes(), encoder=Base64Encoder)

    if args.command == "server":
        print("Starting server")
        app = web.Application()
        app["bootstrap_peers"] = args.bootstrap_peer
        dm = DataMesher(
            state_file=Path(args.state_file),
            host=Host(
                ip=ipaddress.IPv6Address(args.ip),
                port=args.port,
                publicKey=key.verify_key,
            ),
            key=key,
        )
        app["data"] = dm
        app.cleanup_ctx.append(background_tasks)
        web.run_app(server(app), port=args.port)
    elif args.command == "test":
        print(args.bootstrap_peer)
