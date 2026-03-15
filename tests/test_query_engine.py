"""Tests for graph/query_engine.py."""

from pathlib import Path

from codegraph_mcp.graph.builder import GraphBuilder
from codegraph_mcp.graph.query_engine import QueryEngine
from codegraph_mcp.models import GraphQuery


class TestQueryEngine:
    def _make_engine(self, sample_repo_dir: Path) -> QueryEngine:
        builder = GraphBuilder()
        builder.build_from_repository(sample_repo_dir)
        return QueryEngine(builder.graph, builder._node_index)

    def test_search_nodes(self, sample_repo_dir: Path):
        engine = self._make_engine(sample_repo_dir)
        results = engine.search_nodes("index")
        assert len(results) >= 1

    def test_search_nodes_empty(self, sample_repo_dir: Path):
        engine = self._make_engine(sample_repo_dir)
        results = engine.search_nodes("zzz_nonexistent_zzz")
        assert results == []

    def test_trace_dependencies(self, sample_repo_dir: Path):
        engine = self._make_engine(sample_repo_dir)
        # The repo node should have downstream deps (files)
        gq = GraphQuery(node_id=f"repository:{sample_repo_dir.name}")
        deps = engine.trace_dependencies(gq)
        assert len(deps) >= 1

    def test_impact_analysis(self, sample_repo_dir: Path):
        engine = self._make_engine(sample_repo_dir)
        # Find a function node and do impact analysis
        funcs = engine.search_nodes("greet")
        if funcs:
            gq = GraphQuery(node_id=funcs[0].id)
            result = engine.impact_analysis(gq)
            assert result.source_node == funcs[0].id

    def test_architecture_summary(self, sample_repo_dir: Path):
        engine = self._make_engine(sample_repo_dir)
        summary = engine.architecture_summary()
        assert summary.total_nodes > 0
        assert summary.files_analyzed >= 1

    def test_trace_path_nonexistent(self, sample_repo_dir: Path):
        engine = self._make_engine(sample_repo_dir)
        path = engine.trace_path("fake:a", "fake:b")
        assert path == []
