"""Collect development pipeline metrics from git, tests, and coverage."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .metrics import MetricsRegistry, get_registry


@dataclass
class RunResult:
    """Result of a subprocess invocation."""

    stdout: str
    stderr: str
    returncode: int | None


class DevelopmentCollector:
    """Gathers metrics about the development process."""

    def __init__(self, repo_path: str | Path | None = None, registry: MetricsRegistry | None = None) -> None:
        self._repo_path = Path(repo_path or os.getenv("REPO_PATH", "."))
        self._registry = registry or get_registry()

    def _run(self, cmd: list[str]) -> RunResult:
        try:
            result = subprocess.run(
                cmd,
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return RunResult(
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                returncode=result.returncode,
            )
        except FileNotFoundError:
            return RunResult(stdout="", stderr="", returncode=None)

    def collect_git_metrics(self) -> None:
        commit_result = self._run(["git", "rev-list", "--count", "HEAD"])
        files_result = self._run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "HEAD"])

        commit_count = commit_result.stdout if commit_result.returncode is not None and commit_result.returncode == 0 else ""
        files_changed = files_result.stdout if files_result.returncode is not None and files_result.returncode == 0 else ""

        self._registry.gauge("dev_git_commits_total", "Total number of commits").set(float(commit_count or 0))
        self._registry.gauge("dev_git_files_changed", "Files changed in last commit").set(float(len(files_changed.splitlines()) if files_changed else 0))

    def collect_test_metrics(self, coverage_xml: str | Path | None = None) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            # Running inside a pytest test; invoking pytest again would recurse.
            return

        result = self._run([sys.executable, "-m", "pytest", "-q", "--tb=no"])
        if result.returncode is None or result.returncode < 0:
            # pytest is not available or was killed before it could finish.
            return

        # pytest executed; record the run and parse the summary.
        self._registry.counter("dev_test_runs_total", "Total test runs").inc()
        output = f"{result.stdout}\n{result.stderr}"
        failed = sum(int(match) for match in re.findall(r"(\d+) failed", output))
        errors = sum(int(match) for match in re.findall(r"(\d+) errors?", output))
        self._registry.counter("dev_test_failures_total", "Total test failures").inc(failed + errors)

        if coverage_xml:
            self._collect_coverage(coverage_xml)

    def _collect_coverage(self, coverage_xml: str | Path) -> None:
        repo_root = os.path.abspath(self._repo_path)
        xml_path_str = os.path.abspath(os.path.normpath(os.path.join(repo_root, str(coverage_xml))))
        if not (xml_path_str == repo_root or xml_path_str.startswith(f"{repo_root}{os.sep}")):
            return

        xml_path = Path(xml_path_str)
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
