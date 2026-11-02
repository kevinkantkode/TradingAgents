"""The desk command. Subcommands arrive in later tasks."""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="desk")
    parser.add_subparsers(dest="command", required=True)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
