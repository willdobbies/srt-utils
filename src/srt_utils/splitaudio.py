import argparse
import subprocess
from pathlib import Path

import srt

def main():
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

    zfill_pad = len(str(len(srt_lines)))
    for idx, sub in enumerate(srt_lines):
        dur = sub.end - sub.start

        chopidx = str(idx).zfill(zfill_pad)
        chop_outpath = args.audio.with_suffix(f".{chopidx}{args.audio.suffix}")

        cmd = [
            "ffmpeg",
            "-ss",
            str(sub.start.total_seconds()),
            "-i",
            f"{args.audio}",
            "-t",
            str(dur.total_seconds()),
            "-c",
            "copy",
            f"{chop_outpath}",
        ]

        print(f"Execute: {cmd}")
        if args.dry:
            continue
        
        subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()
