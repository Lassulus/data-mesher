from pathlib import Path
import argparse
from .http import run
from .data import DataMesher


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
    args = parser.parse_args()

    if args.command == "server":
        print("Starting server")
        dm = DataMesher(name="testing", state_file=Path(args.state_file))
        run(dm=dm)
