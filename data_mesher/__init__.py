import argparse
import ipaddress
import os
import socket
from pathlib import Path

from nacl.encoding import Base64Encoder
from nacl.signing import SigningKey

from .data import DataMesher, Host
from .http import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["server"],
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
    args = parser.parse_args()

    key_file = Path(args.key_file)
    if not key_file.exists():
        key = SigningKey.generate()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key.encode(Base64Encoder))
    else:
        key = SigningKey(key_file.read_bytes())

    if args.command == "server":
        print("Starting server")
        dm = DataMesher(
            state_file=Path(args.state_file),
            host=Host(
                ip=ipaddress.IPv6Address(args.ip),
                port=args.port,
                publicKey=key.verify_key,
            ),
            key=key,
        )
        run(dm=dm)
