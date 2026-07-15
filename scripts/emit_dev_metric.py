"""Emit development metrics via the observability CLI."""

import subprocess
import sys


def main() -> int:
    coverage_xml = sys.argv[1] if len(sys.argv) > 1 else None
    cmd = [sys.executable, "-m", "return42.observability.cli", "dev-metrics"]
    if coverage_xml:
        cmd.extend(["--coverage-xml", coverage_xml])
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
