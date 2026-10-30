"""Apply ASS styles from a TOML config to one or more subtitle files.

Top-level keys define the default style (the first existing style unless
`Name` is given). Each [[extra-styles]] table creates or updates a named
style, inheriting unset attributes from the default style.

Keys use raw ASS style field names, for example `Fontname`, `PrimaryColour`,
`OutlineColour`, `Outline` and `Bold`. Colours are `#RRGGBB` or `&HAABBGGRR`.

Usage:
    sub-apply-style style.toml track.ass
    sub-apply-style style.toml subtitles/*.ass
"""

import argparse
import copy
import tomllib
from pathlib import Path

import pysubs2

STYLE_FIELDS = {
    "fontname": "fontname",
    "fontsize": "fontsize",
    "primarycolour": "primarycolor",
    "secondarycolour": "secondarycolor",
    "tertiarycolour": "tertiarycolor",
    "outlinecolour": "outlinecolor",
    "backcolour": "backcolor",
    "bold": "bold",
    "italic": "italic",
    "underline": "underline",
    "strikeout": "strikeout",
    "scalex": "scalex",
    "scaley": "scaley",
    "spacing": "spacing",
    "angle": "angle",
    "borderstyle": "borderstyle",
    "outline": "outline",
    "shadow": "shadow",
    "alignment": "alignment",
    "marginl": "marginl",
    "marginr": "marginr",
    "marginv": "marginv",
    "encoding": "encoding",
}
COLOR_ATTRS = {
    "primarycolor",
    "secondarycolor",
    "tertiarycolor",
    "outlinecolor",
    "backcolor",
}
BOOL_ATTRS = {"bold", "italic", "underline", "strikeout"}
INT_ATTRS = {"borderstyle", "marginl", "marginr", "marginv", "encoding"}
FLOAT_ATTRS = {"fontsize", "scalex", "scaley", "spacing", "angle", "outline", "shadow"}


def parse_color(value: str) -> pysubs2.Color:
    """Parse `#RRGGBB` or `&HAABBGGRR` into a pysubs2 colour."""
    if not isinstance(value, str):
        raise TypeError(f"colour must be a string, got {value!r}")

    value = value.strip()
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) != 6:
            raise ValueError(f"expected #RRGGBB, got {value!r}")
        r, g, b = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
        return pysubs2.Color(r, g, b)

    if value[:2].upper() == "&H":
        digits = value[2:].rstrip("&")
        if len(digits) == 6:
            digits = "00" + digits
        if len(digits) != 8:
            raise ValueError(f"expected &HAABBGGRR, got {value!r}")
        a, b, g, r = (int(digits[i : i + 2], 16) for i in (0, 2, 4, 6))
        return pysubs2.Color(r, g, b, a)

    raise ValueError(f"expected #RRGGBB or &HAABBGGRR, got {value!r}")


def convert_value(attr: str, value):
    if attr in COLOR_ATTRS:
        return parse_color(value)
    if attr in BOOL_ATTRS:
        if not isinstance(value, bool):
            raise ValueError(f"{attr} must be true or false")
        return value
    if attr == "alignment":
        return pysubs2.Alignment(int(value))
    if attr in INT_ATTRS:
        return int(value)
    if attr in FLOAT_ATTRS:
        return float(value)
    return str(value)


def apply_options(style: pysubs2.SSAStyle, options: dict) -> None:
    for key, value in options.items():
        attr = STYLE_FIELDS.get(key.lower())
        if attr is None:
            raise ValueError(f"unknown style option: {key}")
        setattr(style, attr, convert_value(attr, value))


def split_name(table: dict) -> tuple[str | None, dict]:
    for key, value in table.items():
        if key.lower() == "name":
            return str(value), {k: v for k, v in table.items() if k != key}
    return None, dict(table)


def get_or_create_style(
    subs: pysubs2.SSAFile, name: str, base: pysubs2.SSAStyle | None = None
) -> pysubs2.SSAStyle:
    if name not in subs.styles:
        subs.styles[name] = copy.deepcopy(
            base if base is not None else pysubs2.SSAStyle()
        )
    return subs.styles[name]


def apply_config(subs: pysubs2.SSAFile, config: dict) -> pysubs2.SSAFile:
    config = dict(config)
    extras = config.pop("extra-styles", [])

    default_name, default_options = split_name(config)
    if default_name is None:
        default_name = next(iter(subs.styles), "Default")

    first_style = next(iter(subs.styles.values()), None)
    default_style = get_or_create_style(subs, default_name, first_style)
    apply_options(default_style, default_options)

    if not isinstance(extras, list):
        raise TypeError("extra-styles must be an array of tables")
    for table in extras:
        name, options = split_name(table)
        if not name:
            raise ValueError("each extra style needs a Name")
        style = get_or_create_style(subs, name, default_style)
        apply_options(style, options)

    for event in subs.events:
        if event.style not in subs.styles:
            event.style = default_name

    return subs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="TOML style config")
    parser.add_argument("subtitles", nargs="+", type=Path, help=".ass files to update")
    parser.add_argument("--format", default=".ass", type=str, help="Output format to use (.ass)")
    parser.add_argument(
        "--encoding", type=str, default="utf-8", help="Encoding of utf-8"
    )
    args = parser.parse_args()

    with args.config.open("rb") as fh:
        config = tomllib.load(fh)

    for path in args.subtitles:
        subs = pysubs2.load(path, encoding=args.encoding)
        apply_config(subs, config)
        path = path.with_suffix(args.format)
        subs.save(path, encoding=args.encoding)
        print(f"styled {path}")


if __name__ == "__main__":
    main()
