import subprocess
import sys
from pathlib import Path

from return42.observability.dev_collector import DevelopmentCollector
from return42.observability.metrics import MetricsRegistry


def test_collect_git_metrics(tmp_path):
    # Initialize a git repo in temp dir
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "test commit"], cwd=tmp_path, check=True, capture_output=True)

    registry = MetricsRegistry()
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

    registry = MetricsRegistry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_git_metrics()

    assert registry.get_sample_values("dev_git_commits_total")[("dev_git_commits_total", ())] == 0.0
    assert registry.get_sample_values("dev_git_files_changed")[("dev_git_files_changed", ())] == 0.0


def test_collect_test_metrics_runs_pytest(tmp_path):
    registry = MetricsRegistry()
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

    registry = MetricsRegistry()
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

    registry = MetricsRegistry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    collector.collect_test_metrics()

    assert not calls
    assert registry.get_sample_values("dev_test_runs_total") == {}
