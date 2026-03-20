"""Graph builder — converts parser output into a NetworkX directed graph."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import networkx as nx

from codegraph_mcp.enums import EdgeType, NodeType
from codegraph_mcp.models import Edge, Node
from codegraph_mcp.parser.base import BaseParser, ParseResult
from codegraph_mcp.parser.java import JavaParser
from codegraph_mcp.parser.kotlin import KotlinParser
from codegraph_mcp.parser.typescript import TypeScriptParser
from codegraph_mcp.utils.scanner import (
    detect_language,
    scan_repository,
)

logger = logging.getLogger("codegraph_mcp.graph.builder")

# Registry: language string → parser instance
_PARSERS: dict[str, BaseParser] = {
    "typescript": TypeScriptParser(),
    "java": JavaParser(),
    "kotlin": KotlinParser(),
}


class GraphBuilder:
    """Incrementally builds a NetworkX DiGraph from a repository."""

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        self._node_index: dict[str, Node] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_from_repository(self, repo_path: Path) -> nx.DiGraph:
        """Scan, parse, and build the graph for an entire repository."""
        start = time.perf_counter()

        # Repository root node
        repo_id = f"repository:{repo_path.name}"
        self._add_node(
            Node(
                id=repo_id,
                type=NodeType.REPOSITORY,
                name=repo_path.name,
            )
        )

        for source_file in scan_repository(repo_path):
            self._process_file(source_file, repo_id)

        elapsed = time.perf_counter() - start
        logger.info(
            "Graph built: %d nodes, %d edges in %.2fs",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
            elapsed,
        )
        return self.graph

    def add_parse_result(self, result: ParseResult) -> None:
        """Merge a ``ParseResult`` into the graph (for incremental use)."""
        for node in result.nodes:
            self._add_node(node)
        for edge in result.edges:
            self._add_edge(edge)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Node | None:
        """Return the parsed ``Node`` for *node_id*, or ``None`` if unknown."""
        return self._node_index.get(node_id)

    def all_nodes(self) -> list[Node]:
        """Return every node currently in the index (order not guaranteed)."""
        return list(self._node_index.values())

    def all_edges(self) -> list[Edge]:
        """Return all edges in the graph, with types taken from edge attributes."""
        edges: list[Edge] = []
        for u, v, data in self.graph.edges(data=True):
            edges.append(Edge(source=u, target=v, type=data.get("type", EdgeType.DEPENDS_ON)))
        return edges

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _process_file(self, path: Path, repo_id: str) -> None:
        """Parse *path* if supported and wire its file node to *repo_id*."""
        language = detect_language(path)
        if language is None:
            return

        parser = _PARSERS.get(language)
        if parser is None:
            logger.debug("No parser for language %s, skipping %s", language, path)
            return

        try:
            source = path.read_bytes()
        except (OSError, PermissionError):
            logger.warning("Cannot read file: %s", path)
            return

        result = parser.parse_file(path, source)
        self.add_parse_result(result)

        # Link file node to repository
        for node in result.nodes:
            if node.type == NodeType.FILE:
                self._add_edge(
                    Edge(
                        source=repo_id,
                        target=node.id,
                        type=EdgeType.DEPENDS_ON,
                    )
                )

    def _add_node(self, node: Node) -> None:
        """Insert *node* into the index and NetworkX graph (first write wins)."""
        if node.id not in self._node_index:
            self._node_index[node.id] = node
            self.graph.add_node(node.id, **node.model_dump())

    def _add_edge(self, edge: Edge) -> None:
        """Add *edge*; create stub endpoints if missing so NetworkX stays consistent."""
        # Ensure both endpoints exist as graph nodes (at minimum as stubs)
        for nid in (edge.source, edge.target):
            if nid not in self.graph:
                self.graph.add_node(nid)
        self.graph.add_edge(edge.source, edge.target, type=edge.type)
