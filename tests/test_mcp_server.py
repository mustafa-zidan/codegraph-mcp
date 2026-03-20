"""Tests for the MCP server tool functions."""

import json
from pathlib import Path

import pytest

from codegraph_mcp.server import mcp_server
from codegraph_mcp.server.mcp_server import (
    architecture_summary,
    impact_analysis,
    initialize,
    search_nodes,
    trace_path,
)


@pytest.fixture(autouse=True)
def _init_server(sample_repo_dir: Path, tmp_path: Path):
    """Initialize the MCP server before each test, and close the store after."""
    db = str(tmp_path / "test.kuzu")
    initialize(str(sample_repo_dir), db)
    yield
    if mcp_server._store is not None:
        mcp_server._store.close()
        mcp_server._store = None
    mcp_server._store_path = None
    mcp_server._builder = None
    mcp_server._engine = None


class TestMCPServer:
    def test_search_nodes(self):
        result = json.loads(search_nodes("index"))
        assert isinstance(result, list)

    def test_architecture_summary(self):
        result = json.loads(architecture_summary())
        assert "total_nodes" in result
        assert result["total_nodes"] > 0

    def test_impact_analysis(self):
        result = json.loads(impact_analysis("fake:nonexistent"))
        assert "source_node" in result
        assert result["affected_nodes"] == []

    def test_trace_path_not_found(self):
        result = json.loads(trace_path("fake:a", "fake:b"))
        assert result == []
