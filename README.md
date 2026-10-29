# SRT Utils

A collection of python cli tools which are useful for manipulating/automating srt stuff

## Available commands

**`sub-cat`** — Print subtitles as plaintext lines

```sh
sub-cat subtitles.srt
```

**`sub-inject`** — Replace subtitle text with lines from a `.txt` file, keeping the original timings.

```sh
sub-inject lines.txt subtitles.srt
```

**`sub-splitaudio`** — Split an audio file into clips multiple using subtitle timings (requires: `ffmpeg`)

```sh
sub-splitaudio subtitles.srt audio.flac
...
audio.001.flac
audio.002.flac
audio.003.flac
```

**`sub-apply-style`** — Mass apply subtitle styling to *.ass files.

```sh
sub-apply-style config.toml subtitles.ass
```

**`sub-fit`** — Retime subtitles to the speech detected in an audio file (requires: `ffmpeg`).
Designed to be run as a cleanup pass on whisper-generated .srts.

```sh
sub-fit subtitles.srt audio.flac --out fitted.srt
```
