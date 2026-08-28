#!/usr/bin/env python3
"""Regression tests for the first-class Spine 3.3 and 3.4 codecs."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def converter_command(converter: Path, *arguments: Path | str) -> list[str]:
    command = [str(converter), *(str(argument) for argument in arguments)]
    if converter.suffix in {".js", ".mjs"}:
        command.insert(0, "node")
    return command


def run(converter: Path, source: Path, target: Path, version: str | None = None) -> None:
    command = converter_command(converter, source, target)
    if version is not None:
        command.extend(["-v", version])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(
            f"Conversion failed ({source.name} -> {target.name}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if not target.is_file() or target.stat().st_size == 0:
        raise AssertionError(
            f"Conversion reported success without creating a nonempty output: {target}\n"
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


def assert_deforms_resolve(data: dict[str, Any]) -> None:
    skins = data.get("skins", {})
    for animation_name, animation in data.get("animations", {}).items():
        for skin_name, skin_deforms in animation.get("deform", {}).items():
            if skin_name not in skins:
                raise AssertionError(
                    f"Animation {animation_name!r} deforms missing skin {skin_name!r}"
                )
            for slot_name, slot_deforms in skin_deforms.items():
                if slot_name not in skins[skin_name]:
                    raise AssertionError(
                        f"Animation {animation_name!r} deforms missing slot "
                        f"{skin_name!r}/{slot_name!r}"
                    )
                for attachment_name in slot_deforms:
                    if attachment_name not in skins[skin_name][slot_name]:
                        raise AssertionError(
                            f"Animation {animation_name!r} deforms missing attachment "
                            f"{skin_name!r}/{slot_name!r}/{attachment_name!r}"
                        )


def mesh_attachment() -> dict[str, Any]:
    return {
        "type": "mesh",
        "uvs": [0, 0, 1, 0, 0, 1],
        "triangles": [0, 1, 2],
        "vertices": [0, 0, 10, 0, 0, 10],
        "hull": 3,
    }


def deform_fixture(version: str, populated_default: bool) -> dict[str, Any]:
    skins: dict[str, Any] = {
        "skinA": {"slot": {"meshA": mesh_attachment()}},
        "default": (
            {"slot": {"meshDefault": mesh_attachment()}}
            if populated_default
            else {}
        ),
        "skinB": {"slot": {"meshB": mesh_attachment()}},
    }
    deform: dict[str, Any] = {
        "skinA": {"slot": {"meshA": [{"vertices": [0.25, 0, 0, 0, 0, 0]}]}},
        "skinB": {"slot": {"meshB": [{"vertices": [0.5, 0, 0, 0, 0, 0]}]}},
    }
    if populated_default:
        deform["default"] = {
            "slot": {"meshDefault": [{"vertices": [0.75, 0, 0, 0, 0, 0]}]}
        }

    return {
        "skeleton": {"spine": version},
        "bones": [{"name": "root"}],
        "slots": [{"name": "slot", "bone": "root"}],
        "skins": skins,
        "animations": {"deform-test": {"deform": deform}},
    }


def test_deform_skin_indexes(converter: Path, version: str) -> None:
    for populated_default in (False, True):
        with tempfile.TemporaryDirectory(prefix="spine-deform-index-") as temporary:
            output = Path(temporary)
            source = output / "fixture.json"
            binary = output / "fixture.SKEL.BYTES"
            decoded_path = output / "decoded.JSON"
            source.write_text(
                json.dumps(deform_fixture(version, populated_default)),
                encoding="utf-8",
            )

            run(converter, source, binary, version)
            run(converter, binary, decoded_path)
            decoded = load_json(decoded_path)
            assert_version(decoded, version)
            assert_deforms_resolve(decoded)

            expected_skins = {"skinA", "skinB"}
            if populated_default:
                expected_skins.add("default")
            if set(decoded.get("skins", {})) != expected_skins:
                raise AssertionError(
                    f"Unexpected skins after {version} binary roundtrip: "
                    f"{set(decoded.get('skins', {}))!r}"
                )

            deform = decoded["animations"]["deform-test"]["deform"]
            if deform["skinA"]["slot"]["meshA"][0]["vertices"][0] != 0.25:
                raise AssertionError("skinA deform moved to a different skin")
            if deform["skinB"]["slot"]["meshB"][0]["vertices"][0] != 0.5:
                raise AssertionError("skinB deform moved to a different skin")
            if populated_default:
                if deform["default"]["slot"]["meshDefault"][0]["vertices"][0] != 0.75:
                    raise AssertionError("default deform moved to a different skin")


def test_argument_errors(converter: Path) -> None:
    result = subprocess.run(
        converter_command(converter, "input.bytes", "output.json"),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        raise AssertionError("Unsupported .bytes input incorrectly returned success")

    result = subprocess.run(
        converter_command(converter, "input.skel"),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        raise AssertionError("Missing output argument incorrectly returned success")

    result = subprocess.run(
        converter_command(converter, "--help"),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError("Explicit --help should return success")


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
        assert_deforms_resolve(roundtripped)
        if signature(roundtripped) != expected_signature:
            raise AssertionError(f"JSON topology changed for {source}")

        run(converter, source, binary, version)
        run(converter, binary, binary_roundtrip)
        from_binary = load_json(binary_roundtrip)
        assert_version(from_binary, version)
        assert_deforms_resolve(from_binary)
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
    test_deform_skin_indexes(args.converter, "3.3.05")
    test_deform_skin_indexes(args.converter, "3.4.02")
    test_argument_errors(args.converter)
    if args.adankelmo is not None:
        test_adankelmo(args.converter, args.adankelmo)


if __name__ == "__main__":
    main()
