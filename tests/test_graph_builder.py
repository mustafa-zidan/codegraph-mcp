"""Tests for graph/builder.py."""

from pathlib import Path

from codegraph_mcp.enums import NodeType
from codegraph_mcp.graph.builder import GraphBuilder


class TestGraphBuilder:
    def test_build_from_sample_repo(self, sample_repo_dir: Path):
        builder = GraphBuilder()
        g = builder.build_from_repository(sample_repo_dir)
        assert g.number_of_nodes() > 0
        assert g.number_of_edges() > 0

    def test_repository_node_created(self, sample_repo_dir: Path):
        builder = GraphBuilder()
        builder.build_from_repository(sample_repo_dir)
        repo_nodes = [n for n in builder.all_nodes() if n.type == NodeType.REPOSITORY]
        assert len(repo_nodes) == 1

    def test_file_node_created(self, sample_repo_dir: Path):
        builder = GraphBuilder()
        builder.build_from_repository(sample_repo_dir)
        file_nodes = [n for n in builder.all_nodes() if n.type == NodeType.FILE]
        assert len(file_nodes) >= 1

    def test_deduplication(self, sample_repo_dir: Path):
        builder = GraphBuilder()
        builder.build_from_repository(sample_repo_dir)
        ids = [n.id for n in builder.all_nodes()]
        assert len(ids) == len(set(ids)), "Node IDs should be unique"
