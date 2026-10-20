import argparse
import sys
from pathlib import Path

import srt

parser = argparse.ArgumentParser(
    description="""Inject .txt lines into an srt file, \
    overwriting subtitle content and maintaining timings"""
)
parser.add_argument("txt", type=Path, help="Path to source .txt file")
parser.add_argument("srt", type=Path, help="Path to destination .srt file")
parser.add_argument("--print", action="store_true", help="Only print .srt text")
args = parser.parse_args()

with open(args.srt, "r") as buf:
    srt_raw = buf.read()
    srt_lines = list(srt.parse(srt_raw))
    #print(f"read {len(srt_parse)} subs from {args.srt}")

with open(args.txt, "r") as buf:
    txt_lines = buf.readlines()
    #print(f"read {len(txt_lines)} text lines from {args.txt}")

if len(txt_lines) != len(srt_lines):
    print("Error: text/srt line count mismatch")
    print(f"{args.txt}: {len(txt_lines)}")
    print(f"{args.srt}: {len(srt_lines)}")
    sys.exit(1)

for idx, sub in enumerate(srt_lines):
    srt_lines[idx].content = txt_lines[idx]

# compile the new subs into srt data format
srt_filled = "".join([s.to_srt() for s in srt_lines])

if(args.print):
    print(srt_filled)
else:
    with open(args.srt, "w") as buf:
        buf.write(srt_filled)
    print(f"Injected {len(srt_lines)} lines to {args.srt}")