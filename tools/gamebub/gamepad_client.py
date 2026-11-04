"""@brief Launch the pinned AV v1 client with optional virtual Xbox button output.

Audio/video stay disabled. Injection requires --gamepad; no driver is installed.
The reference receiver/session implementation remains hash-pinned and isolated.
"""

import argparse
import hashlib
import math
import os
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from gamepad_backend import PROFILES

REVISION = "fba79ac27e7130c80d1f668e3377a0f35b0e8ae7"
REFERENCES = {
    "av_client.py": "a598fdf16b7903e25ab435224e7e6b14e174ef13b9feb22ce02b6868b62f000f",
    "av_protocol.py": "3616d907aa63aa31e29e64d64a2b9933e83113e56c32404341b7bc13723de4e6",
}
HERE = Path(__file__).resolve().parent
CACHE = HERE / "artifacts/controller-runtime" / REVISION


def prepare_reference(directory):
    """@brief Fetch only missing pinned files; reject modified cached sources.

    @param directory Isolated cache destination for the two reviewed reference files.
    @return Absolute path to the pinned reference client.
    """
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name, digest in REFERENCES.items():
        path = directory / name
        if path.exists():
            data = path.read_bytes()
        else:
            url = f"https://raw.githubusercontent.com/AEW2015/moonbub/{REVISION}/host/av-v1/{name}"
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024 or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Pinned AV reference integrity mismatch: {path}")
        if not path.exists():
            with path.open("xb") as output:
                output.write(data)
    return directory / "av_client.py"


def main(argv=None):
    """@brief Start a finite input-only session; Ctrl+C triggers reference cleanup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receiver", default="192.168.0.157")
    parser.add_argument("--bind", default="192.168.0.47")
    parser.add_argument("--seconds", type=float, default=7200)
    parser.add_argument("--gamepad", action="store_true")
    parser.add_argument("--profile", choices=PROFILES, default="standard")
    parser.add_argument("--dll", type=Path)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args(argv)
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 7200:
        parser.error("Duration must be within (0,7200] seconds")
    if args.dll is not None and not args.dll.is_absolute():
        parser.error("The DLL path must be absolute")
    reference = prepare_reference(CACHE)
    log = args.log
    if log is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        log = HERE / "artifacts" / f"controller-{stamp}.jsonl"
    command = [
        sys.executable,
        "-u",
        str(reference),
        "--receiver",
        args.receiver,
        "--bind",
        args.bind,
        "--seconds",
        str(args.seconds),
        "--log",
        str(log.resolve()),
    ]
    if args.gamepad:
        command.append("--gamepad")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(HERE)
    environment["GAMEBUB_CONTROLLER_PROFILE"] = args.profile
    if args.dll is not None:
        environment["GAMEBUB_VIGEM_DLL"] = str(args.dll)
    try:
        return subprocess.run(command, env=environment, check=False).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
