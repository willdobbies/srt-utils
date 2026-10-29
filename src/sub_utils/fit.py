"""Retime subtitles to the speech islands detected in their audio.

Whisper often stretches one line across a long SFX/music bed, or merges several
sentences into one long cue. This tool trims each cue to the speech it covers
and splits cues at significant internal pauses. It never rewrites cue text.

Example:
    sub-fit 05.srt 05.flac --out 05.fit.srt --report 05.fit.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import pysubs2


@dataclass
class Options:
    silence_db: float = -50.0
    min_silence: float = 0.35
    split_gap: float = 0.8
    max_parts: int = 4
    lead: float = 0.05
    tail: float = 0.05
    trim: float = 0.35
    split_min: float = 8.0
    min_duration: float = 0.4


def probe_duration(audio: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(result.stdout)
    except ValueError as exc:
        raise RuntimeError(f"could not read duration of {audio}") from exc


def speech_islands(audio: Path, options: Options) -> list[tuple[float, float]]:
    """Return non-silent spans in seconds, merging short gaps."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(audio),
            "-af",
            f"silencedetect=noise={options.silence_db}dB:d={options.min_silence}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffmpeg failed on {audio}")

    starts = [
        float(value)
        for value in re.findall(r"silence_start:\s*([0-9.]+)", result.stderr)
    ]
    ends = [
        float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", result.stderr)
    ]
    total = probe_duration(audio)

    islands: list[tuple[float, float]] = []
    cursor = 0.0
    for time, is_start in sorted(
        [(value, True) for value in starts] + [(value, False) for value in ends]
    ):
        if is_start:
            if time > cursor:
                islands.append((cursor, min(time, total)))
        else:
            cursor = max(cursor, time)
    if cursor < total:
        islands.append((cursor, total))

    merged: list[tuple[float, float]] = []
    for start, end in islands:
        if merged and start - merged[-1][1] <= options.min_silence:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def split_text(text: str) -> list[str]:
    """Split after sentence punctuation, falling back to clause punctuation."""
    for punctuation in ("。！？!?.", "、，,;；"):
        parts = [
            part for part in re.split(f"(?<=[{punctuation}])", text) if part.strip()
        ]
        if len(parts) > 1:
            return parts
    return [text]


def group_islands(
    islands: list[tuple[float, float]], gap: float
) -> list[list[tuple[float, float]]]:
    groups: list[list[tuple[float, float]]] = [[islands[0]]]
    for island in islands[1:]:
        if island[0] - groups[-1][-1][1] >= gap:
            groups.append([island])
        else:
            groups[-1].append(island)
    return groups


def limit_groups(
    groups: list[list[tuple[float, float]]], limit: int
) -> list[list[tuple[float, float]]]:
    """Merge the closest adjacent groups until at most `limit` remain."""
    while len(groups) > limit:
        gaps = [b[0][0] - a[-1][1] for a, b in pairwise(groups)]
        index = min(range(len(gaps)), key=gaps.__getitem__)
        groups[index : index + 2] = [groups[index] + groups[index + 1]]
    return groups


def distribute(segments: list[str], weights: list[float]) -> list[str] | None:
    """Join contiguous segments into groups roughly proportional to weights."""
    count, parts = len(segments), len(weights)
    if count < parts:
        return None

    prefix = [0]
    for segment in segments:
        prefix.append(prefix[-1] + len(segment))
    total, weight = prefix[-1], sum(weights)

    cuts, start = [], 0
    for index, part_weight in enumerate(weights[:-1]):
        target = total * part_weight / weight
        low = start + 1
        high = count - (parts - 1 - index)
        cut = min(
            range(low, high + 1),
            key=lambda end: abs(prefix[end] - prefix[start] - target),
        )
        cuts.append(cut)
        start = cut

    bounds = [0, *cuts, count]
    return ["".join(segments[a:b]).strip() for a, b in pairwise(bounds)]


def repetitive(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return len(compact) > 7 and (
        bool(re.search(r"(\S)\1{7}", compact))
        or len(set(compact)) / len(compact) < 0.15
    )


def continues(event: pysubs2.SSAEvent, following: pysubs2.SSAEvent | None) -> bool:
    """True when this cue runs into the next one without punctuation, which
    usually means a mid-word split rather than a real cue boundary."""
    return (
        following is not None
        and following.start - event.end <= 50
        and not event.plaintext.rstrip().endswith(tuple("。！？!?.,、，…」』）)】"))
    )


def fit_event(
    event: pysubs2.SSAEvent,
    islands: list[tuple[float, float]],
    options: Options,
    allow_split: bool,
) -> tuple[list[pysubs2.SSAEvent], str]:
    start, end = event.start / 1000, event.end / 1000
    hits = [(a, b) for a, b in islands if min(b, end) - max(a, start) > 0.01]
    if not hits:
        return [event], "no_speech"

    new_start = max(start, hits[0][0] - options.lead)
    new_end = min(end, hits[-1][1] + options.tail)
    if new_end <= new_start:
        return [event], "unchanged"

    groups = group_islands(hits, options.split_gap)
    segments = split_text(event.plaintext)
    can_split = (
        allow_split
        and len(groups) > 1
        and len(segments) > 1
        and end - start >= options.split_min
        and len(event.plaintext.strip()) >= 12
        and not repetitive(event.plaintext)
    )
    if can_split:
        groups = limit_groups(groups, max(1, min(options.max_parts, len(segments))))
    if can_split and len(groups) > 1:
        weights = [group[-1][1] - group[0][0] for group in groups]
        texts = distribute(segments, weights)
        if texts:
            parts = []
            for group, text in zip(groups, texts):
                part = event.copy()
                part.start = round(max(start, group[0][0] - options.lead) * 1000)
                part.end = round(min(end, group[-1][1] + options.tail) * 1000)
                if part.end <= part.start:
                    part.end = part.start + round(options.min_duration * 1000)
                part.text = text
                parts.append(part)
            if all(
                part.plaintext.strip() and part.duration >= options.min_duration * 1000
                for part in parts
            ):
                return parts, "split"

    if max(new_start - start, end - new_end) > options.trim:
        event.start = round(new_start * 1000)
        event.end = round(new_end * 1000)
        return [event], "trim"
    return [event], "unchanged"


def event_json(event: pysubs2.SSAEvent) -> dict:
    return {
        "start": round(event.start / 1000, 3),
        "end": round(event.end / 1000, 3),
        "text": event.plaintext,
    }


def resolve_overlaps(events: list[pysubs2.SSAEvent], min_duration: float) -> None:
    previous = None
    for event in events:
        if previous is not None and event.start < previous.end:
            if previous.end - event.start <= 350:
                event.start = previous.end = (previous.end + event.start) // 2
            else:
                event.start = previous.end + 1
        if event.duration < min_duration * 1000:
            event.end = event.start + round(min_duration * 1000)
        previous = event


def fit_subs(
    subs: pysubs2.SSAFile,
    islands: list[tuple[float, float]],
    options: Options,
) -> tuple[dict[str, int], list[dict]]:
    events = list(subs.events)
    output: list[pysubs2.SSAEvent] = []
    changes: list[dict] = []
    counts = {"trim": 0, "split": 0, "no_speech": 0, "unchanged": 0}

    for index, event in enumerate(events, 1):
        following = events[index] if index < len(events) else None
        before = event_json(event)
        parts, action = fit_event(
            event, islands, options, not continues(event, following)
        )
        output.extend(parts)
        counts[action] += 1
        if action != "unchanged":
            changes.append(
                {
                    "index": index,
                    "action": action,
                    "old": before,
                    "new": [event_json(part) for part in parts],
                }
            )

    output.sort(key=lambda event: event.start)
    resolve_overlaps(output, options.min_duration)
    subs.events = output
    return counts, changes


def main() -> int:
    defaults = Options()
    parser = argparse.ArgumentParser(
        description="Retime subtitles to the speech islands in their audio"
    )
    parser.add_argument("subs", type=Path, help="Subtitle file to retime")
    parser.add_argument("audio", type=Path, help="Audio file to analyze")
    parser.add_argument(
        "-o", "--out", type=Path, help="Output (default: <subs>.fit<suffix>)"
    )
    parser.add_argument("--report", type=Path, help="Write a JSON change report")
    parser.add_argument("--dry", action="store_true", help="Do not write subtitles")
    parser.add_argument(
        "--silence-db",
        type=float,
        default=defaults.silence_db,
        help="Signal level treated as silence (dBFS)",
    )
    parser.add_argument("--min-silence", type=float, default=defaults.min_silence)
    parser.add_argument("--split-gap", type=float, default=defaults.split_gap)
    parser.add_argument("--max-parts", type=int, default=defaults.max_parts)
    parser.add_argument("--encoding", type=str, default="utf-8")
    args = parser.parse_args()

    if not args.subs.is_file():
        parser.error(f"subtitle file not found: {args.subs}")
    if not args.audio.is_file():
        parser.error(f"audio file not found: {args.audio}")

    options = Options(
        silence_db=args.silence_db,
        min_silence=args.min_silence,
        split_gap=args.split_gap,
        max_parts=args.max_parts,
    )
    subs = pysubs2.load(args.subs, encoding=args.encoding)
    cues_in = len(subs.events)
    islands = speech_islands(args.audio, options)
    if not islands:
        print(
            "warning: no speech detected; writing subtitles unchanged",
            file=sys.stderr,
        )

    counts, changes = fit_subs(subs, islands, options)
    out = args.out or args.subs.with_suffix(f".fit{args.subs.suffix}")
    if not args.dry:
        out.parent.mkdir(parents=True, exist_ok=True)
        subs.save(out, encoding=args.encoding)

    if args.report:
        report = {
            "subs": str(args.subs),
            "audio": str(args.audio),
            "summary": {
                "cues_in": cues_in,
                "cues_out": len(subs.events),
                "speech_islands": len(islands),
                **counts,
            },
            "changes": changes,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        f"fitted {cues_in} -> {len(subs.events)} cues "
        f"({counts['trim']} trimmed, {counts['split']} split, "
        f"{counts['no_speech']} without speech); "
        f"{'would write' if args.dry else 'wrote'} {out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
