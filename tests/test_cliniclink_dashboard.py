from fastapi.testclient import TestClient
from return42.cliniclink.api import create_app


def test_dashboard_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "t")
    app = create_app(db_path=str(tmp_path / "d.db"), queue_db_path=str(tmp_path / "q.db"))
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "ClinicLink" in r.text
