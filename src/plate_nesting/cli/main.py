"""CLI entry point for plate-nesting."""

import argparse


def main() -> None:
    ap = argparse.ArgumentParser(description="Steel plate nesting application")
    ap.add_argument("command", choices=["convert"], help="Command to run")
    ap.parse_args()


if __name__ == "__main__":
    main()
