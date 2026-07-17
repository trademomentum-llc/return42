#!/usr/bin/env python3
"""Build Linux binaries and a .deb installer for Return42 ClinicLink using Docker.

Requires:
  - Docker

Usage:
  .venv/bin/python scripts/build_linux_installer.py

Outputs:
  build/Return42-ClinicLink-<version>-linux-x86_64.deb
  build/Return42-ClinicLink-<version>-linux-x86_64.tar.gz
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
LINUX_BUILD_DIR = BUILD_DIR / "linux"
DIST_DIR = LINUX_BUILD_DIR / "dist"
VERSION_FILE = ROOT / "src" / "return42" / "cliniclink" / "__init__.py"


def get_version() -> str:
    text = VERSION_FILE.read_text()
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=")[-1].strip().strip('"')
    raise RuntimeError("Could not determine version")


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def build_binaries() -> None:
    if LINUX_BUILD_DIR.exists():
        shutil.rmtree(LINUX_BUILD_DIR)
    LINUX_BUILD_DIR.mkdir(parents=True)

    run(
        [
            "docker",
            "build",
            "-f",
            str(ROOT / "scripts" / "Dockerfile.linux-build"),
            "-t",
            "return42-linux-build",
            str(ROOT),
        ]
    )

    container_id = (
        subprocess.check_output(
            ["docker", "create", "return42-linux-build"],
            text=True,
        )
        .strip()
    )
    try:
        run(["docker", "cp", f"{container_id}:/build/dist", str(LINUX_BUILD_DIR)])
    finally:
        run(["docker", "rm", container_id])


def build_tarball(version: str) -> Path:
    tarball = BUILD_DIR / f"Return42-ClinicLink-{version}-linux-x86_64.tar.gz"
    pkg_dir = LINUX_BUILD_DIR / "Return42-ClinicLink"
    bin_dir = pkg_dir / "bin"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    bin_dir.mkdir(parents=True)
    for binary in ("r42-cliniclink", "r42-observe"):
        shutil.copy(DIST_DIR / binary, bin_dir / binary)
        (bin_dir / binary).chmod(0o755)
    run(
        [
            "tar",
            "-czf",
            str(tarball),
            "-C",
            str(LINUX_BUILD_DIR),
            "Return42-ClinicLink",
        ]
    )
    return tarball


def build_deb(version: str) -> Path:
    deb_name = f"return42-cliniclink_{version}_amd64"
    pkg_root = LINUX_BUILD_DIR / deb_name
    if pkg_root.exists():
        shutil.rmtree(pkg_root)

    control_dir = pkg_root / "DEBIAN"
    control_dir.mkdir(parents=True)

    bin_dir = pkg_root / "usr" / "local" / "bin"
    bin_dir.mkdir(parents=True)
    for binary in ("r42-cliniclink", "r42-observe"):
        shutil.copy(DIST_DIR / binary, bin_dir / binary)
        (bin_dir / binary).chmod(0o755)

    (control_dir / "control").write_text(
        f"Package: return42-cliniclink\n"
        f"Version: {version}\n"
        f"Section: utils\n"
        f"Priority: optional\n"
        f"Architecture: amd64\n"
        f"Maintainer: TradeMomentum LLC <support@trademomentum.io>\n"
        f"Description: Return42 ClinicLink ambulance-to-clinic handoff\n"
        f" Command-line tools for the Return42 resilient edge mesh,\n"
        f" including ClinicLink and observability utilities.\n"
    )

    deb_path = BUILD_DIR / f"Return42-ClinicLink-{version}-linux-x86_64.deb"
    run(["dpkg-deb", "--build", str(pkg_root), str(deb_path)])
    return deb_path


def main() -> int:
    version = get_version()
    print(f"Building Return42 ClinicLink {version} Linux installer...")
    build_binaries()
    deb_path = build_deb(version)
    tarball = build_tarball(version)
    print(f"\nBuilt:\n  {deb_path}\n  {tarball}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
