import subprocess
import sys
from pathlib import Path

from prometheus_client import CollectorRegistry

from return42.observability.dev_collector import DevelopmentCollector
from return42.observability.metrics import MetricsRegistry


def _isolated_registry() -> MetricsRegistry:
    return MetricsRegistry(registry=CollectorRegistry())


def test_collect_git_metrics(tmp_path):
    # Initialize a git repo in temp dir
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "test commit"], cwd=tmp_path, check=True, capture_output=True)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_git_metrics()

    samples = registry.get_sample_values("dev_git_commits_total")
    assert samples[("dev_git_commits_total", ())] == 1.0

    file_samples = registry.get_sample_values("dev_git_files_changed")
    assert file_samples[("dev_git_files_changed", ())] == 1.0


def test_collect_git_metrics_missing_git(tmp_path, monkeypatch):
    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", raise_file_not_found)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_git_metrics()

    assert registry.get_sample_values("dev_git_commits_total")[("dev_git_commits_total", ())] == 0.0
    assert registry.get_sample_values("dev_git_files_changed")[("dev_git_files_changed", ())] == 0.0


def test_collect_test_metrics_runs_pytest(tmp_path):
    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    # No pytest in empty dir; should not crash
    collector.collect_test_metrics()
    # Counter may or may not exist depending on pytest availability


def test_collect_test_metrics_uses_sys_executable(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    captured = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)

        class Result:
            stdout = "1 passed"
            stderr = ""
            returncode = 0

        return Result()

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", fake_run)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_test_metrics()

    assert captured == [[sys.executable, "-m", "pytest", "-q", "--tb=no"]]
    assert registry.get_sample_values("dev_test_runs_total")[("dev_test_runs_total", ())] == 1.0
    assert registry.get_sample_values("dev_test_failures_total")[("dev_test_failures_total", ())] == 0.0


def test_collect_test_metrics_skips_when_inside_pytest(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_dev_collector.py::test_example")

    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        return type("Result", (), {"stdout": "", "stderr": "", "returncode": 0})()

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", fake_run)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_test_metrics()

    assert not calls
    assert registry.get_sample_values("dev_test_runs_total") == {}


def test_collect_test_metrics_counts_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    def fake_run(cmd, **kwargs):
        class Result:
            stdout = "2 passed, 1 failed, 3 errors"
            stderr = ""
            returncode = 1

        return Result()

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", fake_run)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_test_metrics()

    assert registry.get_sample_values("dev_test_runs_total")[("dev_test_runs_total", ())] == 1.0
    assert registry.get_sample_values("dev_test_failures_total")[("dev_test_failures_total", ())] == 4.0


def test_collect_test_metrics_no_metrics_when_pytest_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("pytest")

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", raise_file_not_found)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_test_metrics()

    assert registry.get_sample_values("dev_test_runs_total") == {}
    assert registry.get_sample_values("dev_test_failures_total") == {}


def test_collect_test_metrics_reads_relative_coverage_xml(tmp_path, monkeypatch):
    """Happy path reads the constant ``coverage.xml`` under the repo root."""
    import builtins
    import os

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    coverage_file = tmp_path / "coverage.xml"
    coverage_file.write_text('<coverage line-rate="0.25"></coverage>')
    (tmp_path / "other.xml").write_text('<coverage line-rate="0.99"></coverage>')

    def fake_run(cmd, **kwargs):
        return type("Result", (), {"stdout": "1 passed", "stderr": "", "returncode": 0})()

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", fake_run)

    opened = []
    real_open = builtins.open

    def tracking_open(file, *args, **kwargs):
        opened.append(os.fspath(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracking_open)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_test_metrics("coverage.xml")

    assert registry.get_sample_values("dev_coverage_percent")[("dev_coverage_percent", ())] == 25.0
    expected = os.path.join(os.path.realpath(tmp_path), "coverage.xml")
    xml_opened = [os.path.realpath(path) for path in opened if path.endswith(".xml")]
    assert xml_opened == [expected]


def test_collect_test_metrics_rejects_path_traversal_coverage_xml(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    outside_file = tmp_path.parent / "outside-coverage.xml"
    outside_file.write_text('<coverage line-rate="0.75"></coverage>')

    def fake_run(cmd, **kwargs):
        return type("Result", (), {"stdout": "1 passed", "stderr": "", "returncode": 0})()

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", fake_run)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_test_metrics("../outside-coverage.xml")

    assert registry.get_sample_values("dev_coverage_percent") == {}


def test_collect_test_metrics_rejects_xml_bomb(tmp_path, monkeypatch):
    """Entity expansion must not be parsed into a coverage metric."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    bomb = """<?xml version="1.0"?>
<!DOCTYPE coverage [
  <!ENTITY a "aaaaaaaaaa">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
]>
<coverage line-rate="&b;"></coverage>
"""
    (tmp_path / "coverage.xml").write_text(bomb)

    def fake_run(cmd, **kwargs):
        return type("Result", (), {"stdout": "1 passed", "stderr": "", "returncode": 0})()

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", fake_run)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_test_metrics("coverage.xml")

    assert registry.get_sample_values("dev_coverage_percent") == {}



def test_collect_coverage_rejects_sibling_symlink_and_absolute(tmp_path, monkeypatch):
    """Absolute paths, directory components, sibling prefixes, and symlinks must not be opened."""
    import builtins
    import os

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    def fake_run(cmd, **kwargs):
        return type("Result", (), {"stdout": "1 passed", "stderr": "", "returncode": 0})()

    monkeypatch.setattr("return42.observability.dev_collector.subprocess.run", fake_run)

    sibling = Path(str(tmp_path) + "-sibling")
    sibling.mkdir()
    outside = sibling / "coverage.xml"
    outside.write_text('<coverage line-rate="0.91"></coverage>')
    # A bare startswith(repo_root) matches this sibling directory. The guard
    # must require the separator so the sibling is not treated as inside.
    assert str(outside).startswith(str(tmp_path))
    assert not str(outside).startswith(str(tmp_path) + os.sep)

    opened = []
    real_open = builtins.open

    def tracking_open(file, *args, **kwargs):
        opened.append(os.fspath(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracking_open)

    registry = _isolated_registry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)

    collector.collect_test_metrics(str(outside))
    collector.collect_test_metrics("../" + sibling.name + "/coverage.xml")
    # Directory component whose basename is the allowed name must not be opened.
    nested = tmp_path / "nested"
    nested.mkdir()
    nested_xml = nested / "coverage.xml"
    nested_xml.write_text('<coverage line-rate="0.33"></coverage>')
    collector.collect_test_metrics("nested/coverage.xml")
    collector.collect_test_metrics("nested\\coverage.xml")
    link = tmp_path / "coverage.xml"
    link.symlink_to(outside)
    collector.collect_test_metrics("coverage.xml")
    (tmp_path / "not-a-file").mkdir()
    collector.collect_test_metrics("not-a-file")
    collector.collect_test_metrics("other.xml")

    assert registry.get_sample_values("dev_coverage_percent") == {}
    outside_real = os.path.realpath(outside)
    nested_real = os.path.realpath(nested_xml)
    assert all(os.path.realpath(p) not in {outside_real, nested_real} for p in opened)
