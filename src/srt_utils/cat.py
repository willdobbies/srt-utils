import argparse
from pathlib import Path

import srt

parser = argparse.ArgumentParser(description="Print out srt lines as plain text")
parser.add_argument("path", type=Path, help="The .srt file to print")
args = parser.parse_args()

with open(args.path, "r") as buf:
    subs = srt.parse(buf.read())
    for sub in subs:
        print(sub)
