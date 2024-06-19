import argparse
import logging
import os
from pathlib import Path

from aiohttp import web
from nacl.encoding import Base64Encoder
from nacl.signing import SigningKey

from .data import DataMesher
from .server import spawn_server

log = logging.getLogger(__name__)


def xdg_config_home() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home)
    return Path.home() / ".config"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["server", "create", "test"],
        default=None,
    )
    parser.add_argument(
        "--state-file",
        help="file to read or write the mesh state to",
        type=Path,
        default="./data_mesher.json",
    )
    parser.add_argument(
        "--dns-file",
        help="file where the hostnames as json lines are stored",
        type=Path,
        default="./data_mesher_dns.json",
    )
    parser.add_argument(
        "--ip",
        required=True,
    )
    parser.add_argument(
        "--port",
        type=int,
        help="port to start the datamesher server on",
        default=7331,
    )
    parser.add_argument(
        "--key-file",
        help="file to read or write the key to",
        type=Path,
        default=xdg_config_home() / "data_mesher" / "key",
    )
    parser.add_argument(
        "--bootstrap-peer",
        help="bootstrap peer to connect to, i.e.: http://[2001:DB8::1]:port",
        action="append",
        default=[],
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO"],
        default="INFO",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.log_level == "INFO" else logging.DEBUG
    )
    log.debug(f"set log level to {args.log_level}")

    if not args.key_file.exists():
        key = SigningKey.generate()
        args.key_file.parent.mkdir(parents=True, exist_ok=True)
        args.key_file.write_bytes(key.encode(Base64Encoder))
    else:
        key = SigningKey(args.key_file.read_bytes(), encoder=Base64Encoder)

    if args.command == "server":
        app = spawn_server(
            data_mesher=DataMesher(
                key=key,
                state_file=args.state_file,
                dns_file=args.dns_file,
            ),
            bootstrap_peers=args.bootstrap_peers,
        )
        web.run_app(app, port=args.port)
    elif args.command == "test":
        log.debug(args.bootstrap_peer)
