import argparse
import subprocess
from pathlib import Path

import pysubs2


def get_split_path(path: Path, index: int, padding: int) -> Path:
    padding = len(str(padding))
    idx_zfill = str(index).zfill(padding)
    return path.with_suffix(f".{idx_zfill}{path.suffix}")


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
        outpath = get_split_path(args.audio, idx, len(subs))
        start_s = f"{sub.start / 1000:.3f}"
        end_s = f"{(sub.end - sub.start) / 1000:.3f}"
        cmd = f"ffmpeg -ss {start_s} -i {input} -t {end_s} -c copy {outpath}"

        print(cmd)

        if args.dry:
            continue

        subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    main()
