#!/usr/bin/env python3
"""Unit tests for compound Spine asset suffix handling."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "tools" / "SpineConverter.py"
SPEC = importlib.util.spec_from_file_location("spine_converter_tool", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def main() -> None:
    assert MODULE.source_suffix(Path("hero.skel.bytes")) == ".skel.bytes"
    assert MODULE.source_suffix(Path("hero.SKEL.BYTES")) == ".skel.bytes"
    assert MODULE.source_suffix(Path("hero.atlas.txt")) == ".atlas.txt"
    assert MODULE.source_suffix(Path("hero.json")) == ".json"

    assert MODULE.determine_output_suffix(".skel.bytes", "same") == ".skel.bytes"
    assert MODULE.determine_output_suffix(".skel.bytes", "other") == ".json"
    assert MODULE.determine_output_suffix(".json", "other") == ".skel"

    source = Path("characters") / "hero.skel.bytes"
    assert MODULE.replace_suffix(source, ".skel.bytes", ".json") == (
        Path("characters") / "hero.json"
    )
    assert MODULE.replace_suffix(source, ".skel.bytes", ".skel.bytes") == source


if __name__ == "__main__":
    main()
