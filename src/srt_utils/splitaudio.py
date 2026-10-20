import argparse
import subprocess
from pathlib import Path

import srt

parser = argparse.ArgumentParser(
    description="Slice an audio file, using .srt subtitles as timings"
)

parser.add_argument("srt", type=Path, help="Path to reference .srt file")
parser.add_argument("audio", type=Path, help="Path to audio file to slice")
parser.add_argument(
    "--dry", action="store_true", help="Show commands without executing"
)
args = parser.parse_args()


with open(args.srt, "r") as buf:
    srt_raw = buf.read()
    srt_lines = list(srt.parse(srt_raw))
    print(f"read {len(srt_lines)} subs from {args.srt}")

# detect output filename format
# audio_name, audio_ext = os.path.splitext(args.audio)
chop_zfill = len(srt_lines) // 10  # get_pot(len(srt_parse))

for idx, sub in enumerate(srt_lines):
    dur = sub.end - sub.start

    chop_outpath = args.audio.name.with_suffix(f"{idx:chop_zfill}.{args.audio.suffix}")

    cmd = [
        "ffmpeg",
        "-ss",
        sub.start,
        "-i",
        f"'{args.audio}'",
        "-t",
        dur,
        f"'{chop_outpath}'",
    ]

    print(f"Execute: {cmd}")
    if args.dry:
        continue
    
    subprocess.run(cmd, shell=True, check=True)
