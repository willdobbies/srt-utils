from pathlib import Path

import pysubs2

from .utils import get_path_format_identifier


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="""Inject .txt lines into a subtitle file, \
        overwriting subtitle content and maintaining timings"""
    )
    parser.add_argument("txt", type=Path, help="Path to source .txt file")
    parser.add_argument("subs", type=Path, help="Path to destination subs file")
    parser.add_argument(
        "--encoding",
        type=str,
        default="utf-8",
        help="Encoding of utf-8",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print subtitle content to screen instead of writing",
    )
    args = parser.parse_args()
    
    subs_format = get_path_format_identifier(args.subs)

    subs = pysubs2.load(args.path, encoding=args.encoding)
    txt : str = args.txt.read_text(encoding=args.encoding)
    txt_lines = txt.split("\n")

    if len(txt_lines) != len(subs):
        print(f"Got line mismatch: txt {len(txt_lines)} != subs {len(subs)}")
        return 1

    for event, line in zip(subs, txt_lines):
        event.plaintext = line

    if(args.print):
        print(subs.to_string(subs_format))
        return 0
    
    subs.to_file(args.subs, subs_format)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
