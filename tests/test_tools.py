import sys
from pathlib import Path

import pysubs2
import pytest

from sub_utils import apply_style as apply_style_module
from sub_utils import cat as cat_module
from sub_utils import inject as inject_module
from sub_utils import splitaudio
from sub_utils.apply_style import apply_config, parse_color
from sub_utils.cat import cat_subs
from sub_utils.inject import inject_text
from sub_utils.splitaudio import get_ffmpeg_split_command, get_split_out_path


def write_subs(path, texts=("Hello", "World")):
    subs = pysubs2.SSAFile()
    subs.append(pysubs2.SSAEvent(start=1000, end=2000, text=texts[0]))
    subs.append(pysubs2.SSAEvent(start=2500, end=4000, text=texts[1]))
    subs.save(path)
    return path


@pytest.fixture
def srt(tmp_path):
    return write_subs(tmp_path / "sample.srt")


@pytest.fixture
def txt(tmp_path):
    path = tmp_path / "lines.txt"
    path.write_text("Alpha\nBeta\n", encoding="utf-8")
    return path


def test_cat_subs_prints_plain_text(srt, capsys):
    cat_subs(pysubs2.load(srt))

    assert capsys.readouterr().out == "Hello\nWorld\n"


def test_inject_text_replaces_text_and_keeps_timings(srt):
    subs = pysubs2.load(srt)

    inject_text(subs, ["Alpha", "Beta"])

    assert [event.plaintext for event in subs] == ["Alpha", "Beta"]
    assert [(event.start, event.end) for event in subs] == [(1000, 2000), (2500, 4000)]


def test_inject_text_rejects_line_count_mismatch(srt):
    subs = pysubs2.load(srt)

    with pytest.raises(ValueError):
        inject_text(subs, ["Only one line"])


def test_get_split_out_path_is_zero_padded(tmp_path):
    audio = tmp_path / "audio.flac"

    assert get_split_out_path(audio, 1, 12).name == "audio.01.flac"


def test_get_ffmpeg_split_command_uses_seconds():
    event = pysubs2.SSAEvent(start=1500, end=4000)

    command = get_ffmpeg_split_command(event, Path("audio.flac"), Path("audio.0.flac"))

    assert "-ss 1.500" in command
    assert "-t 2.500" in command


def test_cat_cli(srt, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sub-cat", str(srt)])

    cat_module.main()

    assert capsys.readouterr().out == "Hello\nWorld\n"


@pytest.mark.parametrize("ext", ["srt", "ass", "vtt"])
def test_inject_cli_round_trips_formats(tmp_path, ext, txt, monkeypatch):
    subs_path = write_subs(tmp_path / f"sample.{ext}")
    monkeypatch.setattr(sys, "argv", ["sub-inject", str(txt), str(subs_path)])

    inject_module.main()

    reloaded = pysubs2.load(subs_path)
    assert [event.plaintext for event in reloaded] == ["Alpha", "Beta"]


def test_inject_cli_print_does_not_write(srt, txt, monkeypatch, capsys):
    original = srt.read_bytes()
    monkeypatch.setattr(sys, "argv", ["sub-inject", "--print", str(txt), str(srt)])

    inject_module.main()

    assert "Alpha" in capsys.readouterr().out
    assert srt.read_bytes() == original


def test_parse_color_formats():
    assert parse_color("#112233") == pysubs2.Color(0x11, 0x22, 0x33)
    assert parse_color("&H80402010") == pysubs2.Color(0x10, 0x20, 0x40, 0x80)


def test_apply_config_uses_raw_ass_names():
    subs = pysubs2.SSAFile()
    subs.styles["Default"] = pysubs2.SSAStyle()
    subs.append(pysubs2.SSAEvent(start=0, end=1000, text="Hi", style="Default"))

    apply_config(
        subs,
        {
            "Fontname": "Noto Sans",
            "Fontsize": 30,
            "PrimaryColour": "#112233",
            "Bold": True,
            "Outline": 3,
            "Alignment": 8,
            "extra-styles": [
                {"Name": "Signs", "PrimaryColour": "#FF0000", "Italic": True}
            ],
        },
    )

    default = subs.styles["Default"]
    assert default.fontname == "Noto Sans"
    assert default.fontsize == 30
    assert default.primarycolor == pysubs2.Color(0x11, 0x22, 0x33)
    assert default.bold is True
    assert default.outline == 3
    assert default.alignment == pysubs2.Alignment.TOP_CENTER

    signs = subs.styles["Signs"]
    assert signs.fontname == "Noto Sans"
    assert signs.primarycolor == pysubs2.Color(255, 0, 0)
    assert signs.italic is True


def test_apply_style_cli(tmp_path, monkeypatch):
    subs_path = tmp_path / "sample.ass"
    subs = pysubs2.SSAFile()
    subs.styles["Default"] = pysubs2.SSAStyle()
    subs.append(pysubs2.SSAEvent(start=0, end=1000, text="Hi", style="Default"))
    subs.save(subs_path)

    config_path = tmp_path / "style.toml"
    config_path.write_text('Fontname = "Noto Sans"\nFontsize = 30\n', encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["sub-apply-style", str(config_path), str(subs_path)]
    )

    apply_style_module.main()

    reloaded = pysubs2.load(subs_path)
    assert reloaded.styles["Default"].fontname == "Noto Sans"
    assert reloaded.styles["Default"].fontsize == 30


def test_splitaudio_cli_dry_run(srt, tmp_path, monkeypatch, capsys):
    audio = tmp_path / "audio.mp3"
    monkeypatch.setattr(sys, "argv", ["sub-splitaudio", "--dry", str(srt), str(audio)])

    splitaudio.main()

    output = capsys.readouterr().out
    assert "ffmpeg -ss 1.000" in output
    assert "ffmpeg -ss 2.500" in output


def test_splitaudio_cli_executes_ffmpeg(srt, tmp_path, monkeypatch):
    audio = tmp_path / "audio.mp3"
    calls = []
    monkeypatch.setattr(
        splitaudio.subprocess,
        "run",
        lambda cmd, shell, check: calls.append((cmd, shell, check)),
    )
    monkeypatch.setattr(sys, "argv", ["sub-splitaudio", str(srt), str(audio)])

    splitaudio.main()

    assert len(calls) == 2
    assert all(shell is True and check is True for _, shell, check in calls)
