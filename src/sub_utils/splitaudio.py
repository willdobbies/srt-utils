import argparse
import subprocess
from pathlib import Path

import pysubs2


def get_split_out_path(input : Path, index: int, padding: int) -> Path:
    padding = len(str(padding))
    idx_zfill = str(index).zfill(padding)
    return input.with_suffix(f".{idx_zfill}{input.suffix}")

def get_ffmpeg_split_command(event : pysubs2.SSAEvent, input : Path, output : Path) -> str:
    start = event.start / 1000
    end = (event.end - event.start) / 1000
    return f"ffmpeg -ss {start:.3f} -i {input} -t {end:.3f} -c copy {output}"

def main():
    parser = argparse.ArgumentParser(
        description="Slice an audio file, using subtitles as timings"
    )

    parser.add_argument("subs", type=Path, help="Path to reference subtitle file")
    parser.add_argument("audio", type=Path, help="Path to audio file to slice")
    parser.add_argument(
        "--dry", action="store_true", help="Show commands without executing"
    )
    args = parser.parse_args()

    subs = pysubs2.load(args.subs, encoding=args.encoding)

    for idx, sub in enumerate(subs):
        outpath = get_split_out_path(args.audio, idx, len(subs))
        cmd = get_ffmpeg_split_command(sub, args.audio, outpath)

        print(cmd)

        if args.dry:
            continue

        subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    main()
