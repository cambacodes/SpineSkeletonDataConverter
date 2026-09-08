#!/usr/bin/env python3
"""Exercise legacy wire formats and cross-version conversions through the CLI."""

import argparse
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest


def binary_fixture(version, nonessential):
    # Hand-authored wire data, independent of the converter's binary writer.
    def string(value):
        data = value.encode("utf-8")
        return bytes([len(data) + 1]) + data

    def floats(*values):
        return struct.pack(">" + "f" * len(values), *values)

    data = string("fixture") + string(version) + floats(16, 16) + bytes([nonessential])
    if nonessential:
        data += string("images/")
    data += b"\x01" + string("root") + floats(0, 0, 0, 1, 1, 0, 0, 0)
    data += b"\x01\x01"
    if nonessential:
        data += bytes.fromhex("9b9b9bff")
    # One slot. In 3.3/3.4 there is no dark color between color and attachment.
    data += b"\x01" + string("slot") + b"\x00" + bytes.fromhex("ffffffff")
    data += string("mesh") + b"\x00\x00\x00\x00"
    # Default skin with an unweighted triangle mesh.
    data += b"\x01\x00\x01" + string("mesh") + b"\x00\x02\x00"
    data += bytes.fromhex("ffffffff") + b"\x03" + floats(0, 0, 1, 0, 0, 1)
    data += b"\x03" + struct.pack(">3H", 0, 1, 2)
    data += b"\x00" + floats(0, 0, 16, 0, 0, 16) + b"\x03"
    if nonessential:
        data += b"\x06" + struct.pack(">6H", 0, 2, 2, 4, 4, 0) + floats(16, 16)
    # No named skins or events. One animation with a stepped scale timeline.
    data += b"\x00\x00\x01" + string("move")
    data += b"\x00\x01\x00\x01\x02\x02" + floats(0, 1, 1) + b"\x01" + floats(1, 2, 3)
    data += b"\x00\x00\x00\x00\x00\x00"
    return data


def mesh(weighted=False):
    return {
        "type": "mesh", "uvs": [0, 0, 1, 0, 0, 1], "triangles": [0, 1, 2],
        "vertices": ([1, 0, 0, 0, 1, 1, 0, 16, 0, 1, 1, 0, 0, 16, 1]
                     if weighted else [0, 0, 16, 0, 0, 16]),
        "hull": 3, "edges": [0, 2, 2, 4, 4, 0], "width": 16, "height": 16,
    }


class LegacyConversions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="spine-legacy-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def convert(self, source, name, version=None, success=True):
        target = self.directory / name
        command = [str(EXE), str(source), str(target)]
        if version:
            command += ["-v", version]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(target.is_file(), result.stdout + result.stderr)
            self.assertGreater(target.stat().st_size, 0)
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Error", result.stderr)
            self.assertFalse(target.exists())
        return target

    def json_source(self, data):
        path = self.directory / "source.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_independent_binary_fixtures(self):
        for version in ("3.3.05", "3.4.02"):
            for nonessential in (False, True):
                with self.subTest(version=version, nonessential=nonessential):
                    source = self.directory / "source.skel"
                    source.write_bytes(binary_fixture(version, nonessential))
                    data = self.read(self.convert(source, "decoded.json"))
                    self.assertEqual(data["skeleton"]["spine"], version)
                    self.assertEqual(data["slots"][0]["attachment"], "mesh")
                    attachment = data["skins"]["default"]["slot"]["mesh"]
                    self.assertEqual(attachment["vertices"], mesh()["vertices"])
                    self.assertEqual(attachment.get("edges"), mesh()["edges"] if nonessential else None)
                    self.assertEqual(attachment["width"], 16 if nonessential else 0)
                    self.assertEqual(attachment["height"], 16 if nonessential else 0)
                    frames = data["animations"]["move"]["bones"]["root"]["scale"]
                    self.assertEqual(frames[0], {"time": 0, "x": 1, "y": 1, "curve": "stepped"})
                    self.assertEqual(frames[1], {"time": 1, "x": 2, "y": 3})
                    binary = self.convert(source, "roundtrip.skel")
                    self.assertEqual(binary.read_bytes(), source.read_bytes())
                    upgraded = self.read(self.convert(source, "upgraded.json", "3.8.75"))
                    self.assertEqual(upgraded["skins"][0]["attachments"]["slot"]["mesh"], attachment)

    def test_skins_and_deforms_across_versions(self):
        for populated_default in (None, False, True):
            skins = {"blue": {"slot": {"mesh": mesh(True)}}, "default": {},
                     "red": {"slot": {"mesh": mesh()}}}
            if populated_default:
                skins["default"] = {"slot": {"mesh": mesh()}}
            elif populated_default is None:
                del skins["default"]
            for name, attachments in skins.items():
                if attachments:
                    attachments["slot"]["linked"] = {
                        "type": "linkedmesh", "parent": "mesh", "skin": name,
                        "deform": False, "width": 0, "height": 0,
                    }
            deform = {name: {"slot": {"mesh": [{"time": 0.5, "offset": 2, "vertices": [i + 0.25]}]}}
                      for i, (name, attachments) in enumerate(skins.items()) if attachments}
            source = self.json_source({
                "skeleton": {"spine": "3.3.05"}, "bones": [{"name": "root"}],
                "slots": [{"name": "slot", "bone": "root"}], "skins": skins,
                "animations": {"move": {"deform": deform}},
            })
            for version in ("3.3.05", "3.4.02"):
                with self.subTest(version=version, populated_default=populated_default):
                    binary = self.convert(source, "converted.skel", version)
                    decoded = self.read(self.convert(binary, "decoded.json", "3.3.05"))
                    self.assertEqual(decoded["animations"]["move"]["deform"], deform)
                    self.assertEqual(decoded["skins"], {k: v for k, v in skins.items() if v})

    def test_legacy_scale_defaults_and_linked_mesh(self):
        source = self.json_source({
            "skeleton": {"spine": "3.3.05"}, "bones": [{"name": "root"}],
            "slots": [{"name": "slot", "bone": "root", "attachment": "linked"}],
            "skins": {"default": {"slot": {"mesh": mesh(), "linked": {
                "type": "linkedmesh", "parent": "mesh", "deform": False,
            }}}},
            "animations": {"move": {"bones": {"root": {"scale": [{"x": 2}, {"time": 1}]}}}},
        })
        for version in ("3.3.05", "3.4.02"):
            with self.subTest(version=version):
                binary = self.convert(source, "linked.skel", version)
                decoded = self.read(self.convert(binary, "decoded.json", "3.3.05"))
                frames = decoded["animations"]["move"]["bones"]["root"]["scale"]
                self.assertEqual(frames, [{"time": 0, "x": 2, "y": 0}, {"time": 1, "x": 0, "y": 0}])
                self.assertFalse(decoded["skins"]["default"]["slot"]["linked"]["deform"])

    def test_legacy_inheritance_and_constraint_order(self):
        source = self.json_source({
            "skeleton": {"spine": "3.4.02"},
            "bones": [{"name": "root"}, {"name": "a", "parent": "root", "inheritScale": False},
                      {"name": "b", "parent": "a", "inheritRotation": False},
                      {"name": "c", "parent": "root", "inheritScale": False, "inheritRotation": False}],
            "slots": [{"name": "path", "bone": "root"}],
            "ik": [{"name": "deep", "bones": ["b"], "target": "root"},
                   {"name": "first", "bones": ["a"], "target": "root"},
                   {"name": "last", "bones": ["c"], "target": "root"}],
            "transform": [{"name": "follow", "bones": ["a"], "target": "c"}],
            "path": [{"name": "track", "bones": ["c"], "target": "path"}],
        })
        data = self.read(self.convert(source, "upgraded.json", "3.8.75"))
        self.assertEqual([b.get("transform", "normal") for b in data["bones"]],
                         ["normal", "noScaleOrReflection", "noRotationOrReflection", "onlyTranslation"])
        self.assertEqual([c.get("order", 0) for c in data["ik"]], [2, 1, 0])
        self.assertEqual(data["path"][0]["order"], 3)
        self.assertEqual(data["transform"][0]["order"], 4)
        binary = self.convert(source, "constraints.skel")
        decoded = self.read(self.convert(binary, "decoded.json", "3.8.75"))
        for key in ("bones", "ik", "transform", "path"):
            self.assertEqual(decoded[key], data[key])

    def test_truncated_binary_fails_without_output(self):
        binary = binary_fixture("3.4.02", True)
        for end in (35, 50, 100, len(binary) - 1):
            with self.subTest(end=end):
                source = self.directory / "truncated.skel"
                source.write_bytes(binary[:end])
                self.convert(source, "invalid.json", "3.8.75", success=False)

    def test_downgrade_timeline_counts(self):
        source = self.json_source({
            "skeleton": {"spine": "4.2.22"}, "bones": [{"name": "root"}],
            "slots": [{"name": "slot", "bone": "root", "attachment": "region"}],
            "skins": [{"name": "default", "attachments": {"slot": {"region": {
                "width": 16, "height": 16, "sequence": {"count": 2},
            }}}}],
            "animations": {"move": {
                "bones": {"root": {"inherit": [{"inherit": "normal"}], "rotate": [{"value": 30}]}},
                "attachments": {"default": {"slot": {"region": {"sequence": [{"mode": "hold", "index": 1}]}}}},
            }},
        })
        for version in ("3.3.05", "3.4.02"):
            with self.subTest(version=version):
                binary = self.convert(source, "downgraded.skel", version)
                decoded = self.read(self.convert(binary, "decoded.json", "3.3.05"))
                self.assertEqual(decoded["animations"]["move"]["bones"]["root"]["rotate"], [{"time": 0, "angle": 30}])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    EXE = args.exe.resolve()
    unittest.main(argv=[__file__, *remaining])
