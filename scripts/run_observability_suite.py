"""Start the local observability stack."""

import subprocess
import sys


def main() -> int:
    return subprocess.run(
        ["docker", "compose", "-f", "docker-compose.observability.yml", "up", "--build", "-d"],
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
