from pathlib import Path

from pysubs2.formats import get_format_identifier


def get_path_format_identifier(path : Path):
    """Return the pysubs2 format identifier from a given file"""
    return get_format_identifier(Path(path).suffix.lower())