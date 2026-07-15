from typer.testing import CliRunner

from return42.observability.cli import app

runner = CliRunner()


def test_emit_event(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCE_LOG_DIR", str(tmp_path))
    result = runner.invoke(app, ["emit-event", "cli.test", "--source", "test", "--payload", '{"n":1}'])
    assert result.exit_code == 0
    assert "accepted" in result.output
    assert list(tmp_path.glob("evidence-*.jsonl"))


def test_dev_metrics():
    result = runner.invoke(app, ["dev-metrics"])
    assert result.exit_code == 0
    assert "Development metrics collected" in result.output


def test_serve_help():
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "Run the observability API server" in result.output
