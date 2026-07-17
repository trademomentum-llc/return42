#!/usr/bin/env python3
"""Build a macOS graphical installer package (.pkg) and .dmg for Return42 ClinicLink.

Requires:
  - Python 3.11+
  - PyInstaller: pip install pyinstaller
  - macOS pkgbuild / productbuild / hdiutil (ships with Xcode / Command Line Tools)

Usage:
  .venv/bin/python scripts/build_macos_installer.py

Outputs:
  build/Return42-ClinicLink-<version>-macOS.pkg
  build/Return42-ClinicLink-<version>-macOS.dmg
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
INSTALLER_DIR = BUILD_DIR / "installer"
PAYLOAD_DIR = INSTALLER_DIR / "payload"
BIN_DIR = INSTALLER_DIR / "bin"
DIST_FILE = ROOT / "src" / "return42" / "cliniclink" / "__init__.py"
TAURI_APP = (
    ROOT
    / "cliniclink-desktop"
    / "src-tauri"
    / "target"
    / "release"
    / "bundle"
    / "macos"
    / "ClinicLink Desktop.app"
)


def get_version() -> str:
    text = DIST_FILE.read_text()
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=")[-1].strip().strip('"')
    raise RuntimeError("Could not determine version")


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def _find_script(name: str) -> str:
    # Prefer a virtual environment if one exists locally, otherwise use PATH.
    venv_script = ROOT / ".venv" / "bin" / name
    if venv_script.exists():
        return str(venv_script)
    path = shutil.which(name)
    if path:
        return path
    raise RuntimeError(f"Could not find {name} script in .venv or PATH")


def build_binaries() -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    for script in ("r42-cliniclink", "r42-observe"):
        run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--onefile",
                "--name",
                script,
                "--distpath",
                str(BIN_DIR),
                _find_script(script),
            ],
            cwd=ROOT,
        )


def stage_payload() -> None:
    if PAYLOAD_DIR.exists():
        shutil.rmtree(PAYLOAD_DIR)
    target_bin = PAYLOAD_DIR / "usr" / "local" / "bin"
    target_bin.mkdir(parents=True)
    for script in ("r42-cliniclink", "r42-observe"):
        shutil.copy(BIN_DIR / script, target_bin / script)
        (target_bin / script).chmod(0o755)

    if not TAURI_APP.exists():
        raise RuntimeError(
            f"Tauri desktop app not found at {TAURI_APP}. "
            "Run 'cd cliniclink-desktop && npm run tauri-build' first."
        )
    target_app = PAYLOAD_DIR / "Applications" / "ClinicLink Desktop.app"
    target_app.parent.mkdir(parents=True)
    shutil.copytree(TAURI_APP, target_app, symlinks=True)


def write_installer_resources(version: str) -> None:
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    (INSTALLER_DIR / "welcome.txt").write_text(
        f"Welcome to the Return42 ClinicLink {version} Installer.\n\n"
        "This installer will install the Return42 command-line tools:\n"
        "  - r42-cliniclink\n"
        "  - r42-observe\n\n"
        "It will also install ClinicLink Desktop in /Applications.\n\n"
        "The command-line tools will be placed in /usr/local/bin.\n"
    )
    (INSTALLER_DIR / "license.txt").write_text(
        "Return42 ClinicLink\n"
        "Copyright (c) 2026 TradeMomentum LLC.\n\n"
        "Licensed under the project license. See the repository for full terms.\n"
    )
    (INSTALLER_DIR / "conclusion.txt").write_text(
        "Return42 ClinicLink has been installed successfully.\n\n"
        "ClinicLink Desktop has been installed in /Applications.\n\n"
        "The following commands are now available in /usr/local/bin:\n"
        "  - r42-cliniclink\n"
        "  - r42-observe\n\n"
        "You may need to open a new terminal window or restart your shell to use them.\n"
    )
    distribution_xml = INSTALLER_DIR / "distribution.xml"
    distribution_xml.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<installer-gui-script minSpecVersion="2">\n'
        f'    <title>Return42 ClinicLink {version}</title>\n'
        f'    <organization>com.trademomentum.return42</organization>\n'
        f'    <domains enable_localSystem="true"/>\n'
        f'    <options customize="never" require-scripts="false" rootVolumeOnly="true" />\n'
        f'    <welcome file="welcome.txt"/>\n'
        f'    <license file="license.txt"/>\n'
        f'    <conclusion file="conclusion.txt"/>\n'
        f'    <pkg-ref id="com.trademomentum.return42.cliniclink" version="{version}" auth="root">cliniclink.pkg</pkg-ref>\n'
        f'    <choices-outline>\n'
        f'        <line choice="default">\n'
        f'            <line choice="com.trademomentum.return42.cliniclink"/>\n'
        f'        </line>\n'
        f'    </choices-outline>\n'
        f'    <choice id="default" title="Return42 ClinicLink" description="Install Return42 ClinicLink command-line tools."/>\n'
        f'    <choice id="com.trademomentum.return42.cliniclink" visible="false">\n'
        f'        <pkg-ref id="com.trademomentum.return42.cliniclink"/>\n'
        f'    </choice>\n'
        f'</installer-gui-script>\n'
    )


def build_pkg(version: str) -> Path:
    component_pkg = INSTALLER_DIR / "cliniclink.pkg"
    product_pkg = BUILD_DIR / f"Return42-ClinicLink-{version}-macOS.pkg"
    run(
        [
            "pkgbuild",
            "--root",
            str(PAYLOAD_DIR),
            "--identifier",
            "com.trademomentum.return42.cliniclink",
            "--version",
            version,
            "--install-location",
            "/",
            str(component_pkg),
        ]
    )
    run(
        [
            "productbuild",
            "--distribution",
            str(INSTALLER_DIR / "distribution.xml"),
            "--resources",
            str(INSTALLER_DIR),
            "--package-path",
            str(INSTALLER_DIR),
            str(product_pkg),
        ]
    )
    return product_pkg


def build_dmg(version: str, pkg_path: Path) -> Path:
    dmg_dir = BUILD_DIR / "dmg"
    if dmg_dir.exists():
        shutil.rmtree(dmg_dir)
    dmg_dir.mkdir()
    shutil.copy(pkg_path, dmg_dir / pkg_path.name)
    dmg_path = BUILD_DIR / f"Return42-ClinicLink-{version}-macOS.dmg"
    if dmg_path.exists():
        dmg_path.unlink()
    run(
        [
            "hdiutil",
            "create",
            "-volname",
            f"Return42 ClinicLink {version}",
            "-srcfolder",
            str(dmg_dir),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ]
    )
    return dmg_path


def main() -> int:
    version = get_version()
    print(f"Building Return42 ClinicLink {version} macOS installer...")
    build_binaries()
    stage_payload()
    write_installer_resources(version)
    pkg_path = build_pkg(version)
    dmg_path = build_dmg(version, pkg_path)
    print(f"\nBuilt:\n  {pkg_path}\n  {dmg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
