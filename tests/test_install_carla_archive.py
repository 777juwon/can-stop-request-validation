"""Small archive checks only; no CARLA package extraction or execution."""

import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.install_carla_archive import install_archive, rename_without_replacement


class ArchiveInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carla-extract-test-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "carla.tar.gz"
        self.destination = self.root / "CARLA_0.9.15"
        self.staging = self.root / "CARLA_0.9.15.extracting"
        self.record = self.root / "record.json"

    def fixture(self, *, extra=None, binary_mode=0o755):
        entries = [("CarlaUE4.sh", b"#!/bin/sh\n# fixture, never executed\n", 0o755),
                   ("CarlaUE4/Binaries/Linux/CarlaUE4-Linux-Shipping", b"fixture-binary\n", binary_mode)]
        if extra:
            entries.extend(extra)
        with tarfile.open(self.archive, mode="w:gz") as bundle:
            for name, body, mode in entries:
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(body), mode
                bundle.addfile(info, io.BytesIO(body))
        return sum(len(body) for _, body, _ in entries)

    def install(self, *, expected_bytes=None):
        return install_archive(self.archive, self.destination,
                               self.archive.stat().st_size if expected_bytes is None else expected_bytes,
                               self.record)

    def test_small_valid_archive_is_recorded_and_renamed(self):
        logical_bytes = self.fixture()
        result = self.install()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertTrue((self.destination / "CarlaUE4.sh").is_file())
        self.assertFalse(self.staging.exists())
        saved = json.loads(self.record.read_text())
        self.assertEqual(saved["member_count"], 2)
        self.assertEqual(saved["logical_extracted_bytes"], logical_bytes)
        self.assertEqual(saved["source_sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertIn("never executed", saved["launcher_body"])
        self.assertGreaterEqual(saved["finished_monotonic_ns"], saved["started_monotonic_ns"])

    def test_path_escape_is_rejected_and_partial_staging_preserved(self):
        self.fixture(extra=[("../escaped.txt", b"must not escape", 0o644)])
        result = self.install()
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error"]["type"], "OutsideDestinationError")
        self.assertTrue((self.staging / "CarlaUE4.sh").is_file())
        self.assertFalse((self.root / "escaped.txt").exists())
        self.assertFalse(self.destination.exists())
        self.assertTrue(result["staging_retained"])

    def test_existing_destination_or_staging_is_not_reused(self):
        self.fixture()
        for path in (self.destination, self.staging):
            with self.subTest(path=path):
                path.mkdir()
                marker = path / "keep.txt"
                marker.write_text("preserve")
                record = self.root / (path.name + ".json")
                result = install_archive(self.archive, self.destination, self.archive.stat().st_size, record)
                self.assertEqual(result["status"], "FAILED")
                self.assertEqual(marker.read_text(), "preserve")
                marker.unlink()
                path.rmdir()

    def test_existing_record_is_never_overwritten(self):
        self.fixture()
        self.record.write_text("preserve")
        with self.assertRaises(FileExistsError):
            self.install()
        self.assertEqual(self.record.read_text(), "preserve")
        self.assertFalse(self.staging.exists())

    def test_size_mismatch_fails_before_extraction(self):
        self.fixture()
        result = self.install(expected_bytes=self.archive.stat().st_size + 1)
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("size mismatch", result["error"]["message"])
        self.assertFalse(self.staging.exists())

    def test_required_binary_must_be_executable(self):
        self.fixture(binary_mode=0o644)
        result = self.install()
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("not executable", result["error"]["message"])
        self.assertTrue(self.staging.exists())
        self.assertFalse(self.destination.exists())

    def test_atomic_final_rename_refuses_even_empty_existing_destination(self):
        self.staging.mkdir()
        self.destination.mkdir()
        with self.assertRaises(FileExistsError):
            rename_without_replacement(self.staging, self.destination)
        self.assertTrue(self.staging.is_dir())
        self.assertTrue(self.destination.is_dir())


if __name__ == "__main__":
    unittest.main()
