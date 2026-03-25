#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Compute a wanda digest for a given wanda spec.

Prints the digest to stdout. Used to produce content-addressed hashes
for cache lookups.
"""
from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

import runfiles

from ci.build.build_common import BuildError, find_ray_root, log


def _wanda_binary() -> str:
    """Get the path to the wanda binary from bazel runfiles."""
    r = runfiles.Create()
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Linux" and machine in ("x86_64", "amd64"):
        return r.Rlocation("wanda_linux_x86_64/file/wanda")
    elif system == "Darwin" and machine in ("arm64", "aarch64"):
        return r.Rlocation("wanda_darwin_arm64/file/wanda")
    else:
        raise BuildError(f"Unsupported platform: {system}-{machine}")


def compute_digest(
    wanda_spec: str,
    ray_root: Path,
    epoch: str | None = None,
) -> str:
    """Run wanda digest and return the digest string.

    Wanda resolves build_args from the OS environment and the env file.
    Callers should ensure the required env vars (PYTHON_VERSION, HOSTTYPE,
    ARCH_SUFFIX, BUILDKITE_BAZEL_CACHE_URL, etc.) are set before calling.

    Args:
        epoch: If set, passed as -epoch flag. If None, wanda uses its default
            (empty string in non-rayci mode).
    """
    wanda = _wanda_binary()

    cmd = [wanda, "digest"]
    if epoch is not None:
        cmd += ["-epoch", epoch]
    cmd += [
        "-env_file",
        str(ray_root / "rayci.env"),
        str(ray_root / wanda_spec),
    ]

    log.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=ray_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise BuildError(f"wanda digest failed (rc={result.returncode}): {stderr}")

    digest = result.stdout.strip()
    if not digest:
        raise BuildError("wanda digest produced empty output")
    return digest


def main():
    parser = argparse.ArgumentParser(
        description="Compute a wanda digest for a wanda spec.",
    )
    parser.add_argument(
        "wanda_spec",
        help="Path to wanda YAML spec relative to ray root "
        "(e.g. ci/docker/ray-core.wanda.yaml)",
    )
    parser.add_argument(
        "--epoch",
        default=None,
        help="Epoch for digest computation. If not set, wanda uses its "
        "default (empty string). Use --epoch=0 for stable cache lookups.",
    )
    args = parser.parse_args()

    try:
        root = find_ray_root()
        epoch = args.epoch
        digest = compute_digest(args.wanda_spec, root, epoch=epoch)
        print(digest)
    except BuildError as e:
        log.error(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
