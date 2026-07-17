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
