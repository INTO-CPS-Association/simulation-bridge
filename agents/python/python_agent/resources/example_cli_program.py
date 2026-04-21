"""Example CLI Python program for Python Agent scaffold projects."""

import argparse
import json


def compute_sum(first: int, second: int) -> dict:
    return {
        "first": first,
        "second": second,
        "sum": first + second,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Example CLI program")
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--second", type=int, required=True)
    args = parser.parse_args()

    print(json.dumps(compute_sum(args.first, args.second)))


if __name__ == "__main__":
    main()
