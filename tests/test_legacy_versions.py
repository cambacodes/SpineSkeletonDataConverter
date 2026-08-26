#!/usr/bin/env python3
"""Regression tests for the first-class Spine 3.3 and 3.4 codecs."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def run(converter: Path, source: Path, target: Path, version: str | None = None) -> None:
    command = [str(converter), str(source), str(target)]
    if converter.suffix in {".js", ".mjs"}:
        command.insert(0, "node")
    if version is not None:
        command.extend(["-v", version])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(
            f"Conversion failed ({source.name} -> {target.name}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def signature(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "bones": [bone.get("name") for bone in data.get("bones", [])],
        "slots": [slot.get("name") for slot in data.get("slots", [])],
        "ik": [constraint.get("name") for constraint in data.get("ik", [])],
        "transform": [constraint.get("name") for constraint in data.get("transform", [])],
        "path": [constraint.get("name") for constraint in data.get("path", [])],
        "skins": sorted(data.get("skins", {}).keys()),
        "events": sorted(data.get("events", {}).keys()),
        "animations": sorted(data.get("animations", {}).keys()),
    }


def assert_version(data: dict[str, Any], version: str) -> None:
    actual = data.get("skeleton", {}).get("spine")
    if actual != version:
        raise AssertionError(f"Expected Spine version {version}, got {actual!r}")


def test_fixture(converter: Path, source: Path, version: str, cross_version: str) -> None:
    original = load_json(source)
    expected_signature = signature(original)
    if not expected_signature["bones"] or not expected_signature["animations"]:
        raise AssertionError(f"Fixture is not structurally useful: {source}")

    with tempfile.TemporaryDirectory(prefix="spine-legacy-") as temporary:
        output = Path(temporary)
        json_roundtrip = output / "roundtrip.json"
        binary = output / "roundtrip.skel"
        binary_roundtrip = output / "binary-roundtrip.json"
        cross = output / "cross.json"

        run(converter, source, json_roundtrip, version)
        roundtripped = load_json(json_roundtrip)
        assert_version(roundtripped, version)
        if signature(roundtripped) != expected_signature:
            raise AssertionError(f"JSON topology changed for {source}")

        run(converter, source, binary, version)
        run(converter, binary, binary_roundtrip)
        from_binary = load_json(binary_roundtrip)
        assert_version(from_binary, version)
        if signature(from_binary) != expected_signature:
            raise AssertionError(f"Binary topology changed for {source}")

        run(converter, source, cross, cross_version)
        assert_version(load_json(cross), cross_version)


def test_adankelmo(converter: Path, source: Path) -> None:
    if not source.is_file():
        raise AssertionError(f"Adankelmo fixture does not exist: {source}")

    with tempfile.TemporaryDirectory(prefix="spine-adankelmo-") as temporary:
        output = Path(temporary)
        decoded = output / "adankelmo.json"
        converted = output / "adankelmo-34.skel"
        reread = output / "adankelmo-34.json"

        run(converter, source, decoded)
        legacy = load_json(decoded)
        assert_version(legacy, "3.3.05")
        legacy_signature = signature(legacy)
        if len(legacy_signature["bones"]) < 100 or not legacy_signature["animations"]:
            raise AssertionError("Adankelmo did not decode as a complete animation")

        run(converter, source, converted, "3.4.02")
        run(converter, converted, reread)
        upgraded = load_json(reread)
        assert_version(upgraded, "3.4.02")
        if signature(upgraded) != legacy_signature:
            raise AssertionError("Adankelmo topology changed during 3.3 -> 3.4 binary conversion")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--converter", type=Path, required=True)
    parser.add_argument("--fixtures-root", type=Path, required=True)
    parser.add_argument("--adankelmo", type=Path)
    args = parser.parse_args()

    test_fixture(
        args.converter,
        args.fixtures_root / "33" / "tank" / "export" / "tank.json",
        "3.3.07",
        "3.4.02",
    )
    test_fixture(
        args.converter,
        args.fixtures_root / "34" / "goblins" / "export" / "goblins-mesh.json",
        "3.4.02",
        "3.3.07",
    )
    if args.adankelmo is not None:
        test_adankelmo(args.converter, args.adankelmo)


if __name__ == "__main__":
    main()
