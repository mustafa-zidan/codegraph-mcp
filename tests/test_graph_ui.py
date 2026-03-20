"""Optional HTTP graph viewer routes."""

from pathlib import Path

from starlette.testclient import TestClient

from codegraph_mcp.server import mcp_server


def test_api_graph_returns_payload_when_graph_ui_enabled(tmp_path: Path, sample_repo_dir: Path) -> None:
    db = str(tmp_path / "graph.db")
    mcp_server.initialize(str(sample_repo_dir), db, graph_ui=True)
    app = mcp_server.mcp.streamable_http_app()
    client = TestClient(app)
    r = client.get("/api/graph?limit=200")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data and "edges" in data
    assert "truncated" in data
    assert len(data["nodes"]) > 0
    r2 = client.get("/graph")
    assert r2.status_code == 200
    assert b"vis-network" in r2.content or b"CodeGraph" in r2.content
    if mcp_server._store is not None:
        mcp_server._store.close()
        mcp_server._store = None
