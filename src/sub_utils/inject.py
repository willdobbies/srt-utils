from pathlib import Path

import pysubs2

from .utils import get_path_format_identifier


def inject_text(subs : pysubs2.SSAFile, lines : list) -> pysubs2.SSAFile:
    if len(lines) != len(subs):
        raise ValueError(f"Got line mismatch: txt {len(lines)} != subs {len(subs)}")

    for event, line in zip(subs, lines):
        event.plaintext = line
    
    return subs

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
    txt = args.txt.read_text(encoding=args.encoding)
    txt_lines = txt.split("\n")

    subs = inject_text(subs, txt_lines)

    if(args.print):
        print(subs.to_string(subs_format))
    
    subs.to_file(args.subs, subs_format)


if __name__ == "__main__":
    main()
