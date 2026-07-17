from typer.testing import CliRunner
from return42.cliniclink.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "gateway" in result.output


def test_gateway_help():
    result = runner.invoke(app, ["gateway", "--help"])
    assert result.exit_code == 0
    assert "--node-id" in result.output
    assert "--api-port" in result.output
    assert "--api-host" in result.output


def test_cli_has_sidecar_command():
    from return42.cliniclink.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["sidecar", "--help"])
    assert result.exit_code == 0
    assert "sidecar" in result.output.lower()
