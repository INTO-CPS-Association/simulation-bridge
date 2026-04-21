"""Standalone example script to be executed by Python Agent."""

import argparse
import json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Example CLI program")
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--second", type=int, required=True)
    args = parser.parse_args()

    print(json.dumps({"first": args.first, "second": args.second, "sum": args.first + args.second}))
