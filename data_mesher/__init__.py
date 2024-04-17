import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["server"],
        default=None,
    )
    args = parser.parse_args()

    if args.command == "server":
        print("Starting server")


if __name__ == "__main__":
    main()
