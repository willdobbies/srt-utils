import sys
from types import SimpleNamespace

import pysubs2

from sub_utils import fit
from sub_utils.fit import (
    Options,
    distribute,
    fit_subs,
    group_islands,
    speech_islands,
    split_text,
)


def make_subs(*events):
    subs = pysubs2.SSAFile()
    for start, end, text in events:
        subs.append(pysubs2.SSAEvent(start=start, end=end, text=text))
    return subs


def test_speech_islands_parses_ffmpeg_silence(tmp_path, monkeypatch):
    audio = tmp_path / "audio.flac"
    audio.write_bytes(b"")
    stderr = (
        "[silencedetect @ 0x0] silence_start: 1.0\n"
        "[silencedetect @ 0x0] silence_end: 2.0 | silence_duration: 1.0\n"
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stderr=stderr)

    monkeypatch.setattr(fit.subprocess, "run", fake_run)
    monkeypatch.setattr(fit, "probe_duration", lambda path: 3.0)

    islands = speech_islands(audio, Options())

    assert islands == [(0.0, 1.0), (2.0, 3.0)]
    assert "silencedetect=noise=-50.0dB:d=0.35" in calls[0]


def test_split_text_prefers_sentences():
    assert split_text("こんにちは。元気ですか？") == ["こんにちは。", "元気ですか？"]


def test_split_text_falls_back_to_clauses():
    assert split_text("はい、そうです") == ["はい、", "そうです"]


def test_split_text_without_punctuation_is_one_part():
    assert split_text("hello world") == ["hello world"]


def test_group_islands_uses_gap():
    islands = [(0.0, 1.0), (1.2, 2.0), (3.0, 4.0)]

    assert group_islands(islands, 0.5) == [
        [(0.0, 1.0), (1.2, 2.0)],
        [(3.0, 4.0)],
    ]


def test_distribute_follows_weights():
    assert distribute(["aaaa", "bb", "cccccc"], [1, 1]) == ["aaaabb", "cccccc"]
    assert distribute(["a"], [1, 1]) is None


def test_fit_trims_cue_to_island():
    subs = make_subs((0, 5000, "Hello"))

    counts, changes = fit_subs(subs, [(1.0, 2.0)], Options())

    event = subs.events[0]
    assert (event.start, event.end) == (950, 2050)
    assert counts["trim"] == 1
    assert changes[0]["action"] == "trim"


def test_fit_splits_cue_at_internal_pause():
    subs = make_subs((0, 10000, "こんにちは。元気ですか？"))

    counts, _ = fit_subs(subs, [(0.5, 4.5), (6.0, 9.5)], Options())

    assert counts["split"] == 1
    assert [event.plaintext for event in subs.events] == [
        "こんにちは。",
        "元気ですか？",
    ]
    assert [(event.start, event.end) for event in subs.events] == [
        (450, 4550),
        (5950, 9550),
    ]


def test_fit_leaves_cue_without_speech():
    subs = make_subs((1000, 2000, "Hello"))

    counts, changes = fit_subs(subs, [(3.0, 4.0)], Options())

    assert counts["no_speech"] == 1
    assert changes[0]["action"] == "no_speech"
    assert (subs.events[0].start, subs.events[0].end) == (1000, 2000)


def test_fit_does_not_split_into_a_continuing_cue():
    subs = make_subs(
        (0, 10000, "はい、そうです"),
        (10000, 11000, "next"),
    )

    counts, _ = fit_subs(subs, [(0.5, 4.5), (6.0, 9.5)], Options())

    assert counts["split"] == 0
    assert len(subs.events) == 2


def test_fit_cli_writes_output(tmp_path, monkeypatch):
    subs = make_subs((0, 5000, "Hello"))
    subs_path = tmp_path / "sample.srt"
    subs.save(subs_path)
    audio = tmp_path / "audio.flac"
    audio.write_bytes(b"")
    out = tmp_path / "out.srt"

    monkeypatch.setattr(fit, "speech_islands", lambda *args: [(1.0, 2.0)])
    monkeypatch.setattr(
        sys, "argv", ["sub-fit", str(subs_path), str(audio), "--out", str(out)]
    )

    fit.main()

    reloaded = pysubs2.load(out)
    assert [(event.start, event.end) for event in reloaded] == [(950, 2050)]
