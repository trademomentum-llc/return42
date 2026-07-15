"""Collect development pipeline metrics from git, tests, and coverage."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .metrics import MetricsRegistry, get_registry


class DevelopmentCollector:
    """Gathers metrics about the development process."""

    def __init__(self, repo_path: str | Path | None = None, registry: MetricsRegistry | None = None) -> None:
        self._repo_path = Path(repo_path or os.getenv("REPO_PATH", "."))
        self._registry = registry or get_registry()

    def _run(self, cmd: list[str]) -> str:
        try:
            result = subprocess.run(
                cmd,
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip()
        except FileNotFoundError:
            return ""

    def collect_git_metrics(self) -> None:
        commit_count = self._run(["git", "rev-list", "--count", "HEAD"])
        files_changed = self._run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "HEAD"])
        self._registry.gauge("dev_git_commits_total", "Total number of commits").set(float(commit_count or 0))
        self._registry.gauge("dev_git_files_changed", "Files changed in last commit").set(float(len(files_changed.splitlines()) if files_changed else 0))

    def collect_test_metrics(self, coverage_xml: str | Path | None = None) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            # Running inside a pytest test; invoking pytest again would recurse.
            return

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--tb=no"],
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            output = result.stdout + result.stderr
            self._registry.counter("dev_test_runs_total", "Total test runs").inc()
            # Parse "X passed, Y failed" from pytest summary
            failed = 0
            for part in output.split(","):
                part = part.strip()
                if "failed" in part:
                    failed = int(part.split()[0])
            self._registry.counter("dev_test_failures_total", "Total test failures").inc(failed)

            if coverage_xml:
                self._collect_coverage(coverage_xml)
        except FileNotFoundError:
            # pytest not installed in environment
            pass

    def _collect_coverage(self, coverage_xml: str | Path) -> None:
        xml_path = Path(coverage_xml)
        if not xml_path.exists():
            return
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(xml_path)
            root = tree.getroot()
            rate = root.attrib.get("line-rate", "0")
            self._registry.gauge("dev_coverage_percent", "Code coverage percentage").set(float(rate) * 100)
        except Exception:
            pass

    def emit_all(self, coverage_xml: str | Path | None = None) -> None:
        self.collect_git_metrics()
        self.collect_test_metrics(coverage_xml)
