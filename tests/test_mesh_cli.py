from typer.testing import CliRunner

from return42.mesh.cli import app

runner = CliRunner()


def test_mesh_node_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "mesh-node" in result.output
