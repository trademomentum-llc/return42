import subprocess
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


def test_collect_test_metrics_runs_pytest(tmp_path):
    registry = MetricsRegistry()
    collector = DevelopmentCollector(repo_path=tmp_path, registry=registry)
    # No pytest in empty dir; should not crash
    collector.collect_test_metrics()
    # Counter may or may not exist depending on pytest availability
