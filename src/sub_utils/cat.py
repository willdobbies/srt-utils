import argparse
from pathlib import Path

import pysubs2


def cat_subs(subs: pysubs2.SSAFile):
    for line in [event.plaintext for event in subs]:
        print(line)


def main():
    parser = argparse.ArgumentParser(
        description="Print out subtitle lines as plain text"
    )
    parser.add_argument("subs", type=Path, help="The subs file to print")
    parser.add_argument(
        "--encoding", type=str, default="utf-8", help="Encoding of utf-8"
    )
    args = parser.parse_args()

    subs = pysubs2.load(args.path, encoding=args.encoding)
    cat_subs(subs)


if __name__ == "__main__":
    main()
