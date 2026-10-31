#!/usr/bin/env python3
"""Extract a local CARLA archive without executing or downloading its contents.

Existing destination, destination.extracting and record paths are never reused.
Failed staging directories are retained for inspection. The SHA256 is a local
provenance record, not verification against an upstream published checksum.
"""

from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import tarfile
import time


LAUNCHER = Path("CarlaUE4.sh")
BINARY = Path("CarlaUE4/Binaries/Linux/CarlaUE4-Linux-Shipping")
MAX_LAUNCHER_BYTES = 64 * 1024


def rename_without_replacement(source: Path, destination: Path) -> None:
    """Linux atomic rename that also refuses a concurrently created target."""
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exc:
        raise OSError("Linux renameat2 is required for a non-replacing final rename") from exc
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_executables(staging: Path) -> dict:
    checks = {}
    for relative in (LAUNCHER, BINARY):
        path = staging / relative
        if not path.resolve().is_relative_to(staging.resolve()):
            raise ValueError(f"Required executable resolves outside staging: {relative}")
        if not path.is_file():
            raise ValueError(f"Required executable is missing or not a file: {relative}")
        mode = stat.S_IMODE(path.stat().st_mode)
        if not mode & 0o111 or not os.access(path, os.X_OK):
            raise ValueError(f"Required file is not executable: {relative}")
        checks[str(relative)] = {"size_bytes": path.stat().st_size, "mode": oct(mode)}
    with (staging / LAUNCHER).open("rb") as stream:
        launcher = stream.read(MAX_LAUNCHER_BYTES + 1)
    if len(launcher) > MAX_LAUNCHER_BYTES:
        raise ValueError("Launcher exceeds 64 KiB inspection limit")
    return {"required_files": checks, "launcher_body": launcher.decode("utf-8", errors="replace"),
            "launcher_sha256": hashlib.sha256(launcher).hexdigest()}


def install_archive(archive: Path, destination: Path, expected_bytes: int, record: Path) -> dict:
    archive, destination, record = (p.absolute() for p in (archive, destination, record))
    staging = destination.with_name(destination.name + ".extracting")
    # A record inside staging/destination would create or mutate the very paths
    # whose absence is a prerequisite, so reject this before creating anything.
    if any(record.resolve().is_relative_to(p.resolve()) for p in (destination, staging)):
        raise ValueError("Record must be outside destination and staging")
    record.parent.mkdir(parents=True, exist_ok=True)
    evidence = {
        "status": "STARTED", "archive": str(archive), "destination": str(destination),
        "staging": str(staging), "record": str(record), "expected_bytes": expected_bytes,
        "actual_bytes": None, "source_sha256": None, "member_count": None,
        "logical_extracted_bytes": None, "launcher_body": None,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "started_monotonic_ns": time.monotonic_ns(), "python_version": sys.version,
        "tar_filter": "data", "error": None,
        "checksum_scope": "Locally observed SHA256; no upstream checksum comparison",
    }
    with record.open("x", encoding="utf-8") as output:
        def save() -> None:
            output.seek(0)
            json.dump(evidence, output, indent=2, ensure_ascii=False, allow_nan=False)
            output.write("\n")
            output.truncate()
            output.flush()

        save()
        try:
            if expected_bytes <= 0:
                raise ValueError("expected-bytes must be positive")
            for path in (destination, staging):
                if os.path.lexists(path):
                    raise FileExistsError(f"Refusing existing path: {path}")
            if not hasattr(tarfile, "data_filter"):
                raise RuntimeError("This Python needs tarfile.data_filter support")
            if not archive.is_file():
                raise ValueError("Archive is missing or not a file")
            evidence["actual_bytes"] = archive.stat().st_size
            if evidence["actual_bytes"] != expected_bytes:
                raise ValueError(f"Archive size mismatch: {evidence['actual_bytes']} != {expected_bytes}")
            evidence["source_sha256"] = file_sha256(archive)
            save()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive, mode="r:*") as bundle:
                members = bundle.getmembers()
                evidence["member_count"] = len(members)
                evidence["logical_extracted_bytes"] = sum(m.size for m in members if m.isfile())
                evidence["logical_bytes_scope"] = "Sum of regular-file member sizes, not allocated disk bytes"
                save()
                staging.mkdir(exist_ok=False)
                bundle.extractall(path=staging, filter="data")
            evidence.update(validate_executables(staging))
            save()
            rename_without_replacement(staging, destination)
            evidence["status"] = "COMPLETE"
        except (Exception, KeyboardInterrupt) as exc:
            evidence["status"] = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED"
            evidence["error"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            evidence["finished_utc"] = datetime.now(timezone.utc).isoformat()
            evidence["finished_monotonic_ns"] = time.monotonic_ns()
            evidence["staging_retained"] = os.path.lexists(staging)
            save()
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    def terminated(_signum, _frame):
        raise KeyboardInterrupt("SIGTERM")
    signal.signal(signal.SIGTERM, terminated)
    try:
        result = install_archive(args.archive, args.destination, args.expected_bytes, args.record)
    except (OSError, ValueError) as exc:
        print(f"Cannot start extraction: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "record": result["record"], "error": result["error"]}))
    return {"COMPLETE": 0, "FAILED": 2, "INTERRUPTED": 130}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
