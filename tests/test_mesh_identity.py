from return42.mesh.identity import NodeIdentity


def test_node_identity_creation():
    node = NodeIdentity(node_id="som-01")
    assert node.node_id == "som-01"
    assert node.public_key is not None


def test_node_identity_from_env(monkeypatch):
    monkeypatch.setenv("NODE_ID", "som-02")
    node = NodeIdentity.from_env()
    assert node.node_id == "som-02"
