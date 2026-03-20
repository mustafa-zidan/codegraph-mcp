"""Query engine — graph traversal algorithms on the code knowledge graph."""

from __future__ import annotations

import logging
import time
from collections import deque

import networkx as nx

from codegraph_mcp.enums import EdgeType, NodeType
from codegraph_mcp.models import (
    ArchitectureSummary,
    Edge,
    GraphQuery,
    ImpactResult,
    Node,
)

logger = logging.getLogger("codegraph_mcp.graph.query_engine")


class QueryEngine:
    """Executes queries against a built NetworkX graph."""

    def __init__(self, graph: nx.DiGraph, node_index: dict[str, Node] | None = None) -> None:
        self._g = graph
        self._nodes = node_index or {}

    # ------------------------------------------------------------------
    # MCP tool: search_nodes
    # ------------------------------------------------------------------

    def search_nodes(
        self,
        query: str,
        node_type: NodeType | None = None,
        limit: int = 50,
    ) -> list[Node]:
        """Return nodes whose name contains *query* (case-insensitive)."""
        start = time.perf_counter()
        query_lower = query.lower()
        matches: list[Node] = []
        for node in self._nodes.values():
            if node_type and node.type != node_type:
                continue
            if query_lower in node.name.lower() or query_lower in node.id.lower():
                matches.append(node)
                if len(matches) >= limit:
                    break
        logger.info("search_nodes(%r) → %d results in %.3fs", query, len(matches), time.perf_counter() - start)
        return matches

    # ------------------------------------------------------------------
    # MCP tool: trace_dependencies (downstream)
    # ------------------------------------------------------------------

    def trace_dependencies(self, gq: GraphQuery) -> list[Node]:
        """BFS downstream — what does *node_id* depend on?"""
        return self._bfs(gq.node_id, gq.max_depth, successors=True)

    # ------------------------------------------------------------------
    # MCP tool: trace_dependents (upstream)
    # ------------------------------------------------------------------

    def trace_dependents(self, gq: GraphQuery) -> list[Node]:
        """BFS upstream — what depends on *node_id*?"""
        return self._bfs(gq.node_id, gq.max_depth, successors=False)

    # ------------------------------------------------------------------
    # MCP tool: impact_analysis
    # ------------------------------------------------------------------

    def impact_analysis(self, gq: GraphQuery) -> ImpactResult:
        """BFS upstream to determine everything affected by a change to *node_id*."""
        start = time.perf_counter()
        affected = self._bfs(gq.node_id, gq.max_depth, successors=False)
        affected_edges: list[Edge] = []

        affected_ids = {n.id for n in affected} | {gq.node_id}
        for u, v, data in self._g.edges(data=True):
            if u in affected_ids and v in affected_ids:
                affected_edges.append(
                    Edge(
                        source=u,
                        target=v,
                        type=data.get("type", EdgeType.DEPENDS_ON),
                    )
                )

        logger.info("impact_analysis(%s) → %d nodes in %.3fs", gq.node_id, len(affected), time.perf_counter() - start)
        return ImpactResult(
            source_node=gq.node_id,
            affected_nodes=affected,
            affected_edges=affected_edges,
            depth=gq.max_depth,
        )

    # ------------------------------------------------------------------
    # MCP tool: trace_path
    # ------------------------------------------------------------------

    def trace_path(self, source_id: str, target_id: str) -> list[Node]:
        """Shortest path between *source_id* and *target_id* (undirected graph).

        Only nodes present in the internal index are included; intermediate
        graph ids without metadata are skipped.
        """
        try:
            path_ids = nx.shortest_path(self._g.to_undirected(), source_id, target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
        return [self._nodes[nid] for nid in path_ids if nid in self._nodes]

    # ------------------------------------------------------------------
    # MCP tool: architecture_summary
    # ------------------------------------------------------------------

    def architecture_summary(self) -> ArchitectureSummary:
        """Return a compact high-level summary of the graph."""
        node_counts: dict[str, int] = {}
        languages: set[str] = set()
        files_analyzed = 0

        for node in self._nodes.values():
            key = node.type.value
            node_counts[key] = node_counts.get(key, 0) + 1
            if node.type == NodeType.FILE:
                files_analyzed += 1
            if node.language:
                languages.add(node.language)

        edge_counts: dict[str, int] = {}
        for _, _, data in self._g.edges(data=True):
            etype = data.get("type", EdgeType.DEPENDS_ON)
            key = etype.value if isinstance(etype, EdgeType) else str(etype)
            edge_counts[key] = edge_counts.get(key, 0) + 1

        return ArchitectureSummary(
            total_nodes=self._g.number_of_nodes(),
            total_edges=self._g.number_of_edges(),
            node_counts=node_counts,
            edge_counts=edge_counts,
            files_analyzed=files_analyzed,
            languages=sorted(languages),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bfs(
        self,
        start: str,
        max_depth: int,
        *,
        successors: bool,
    ) -> list[Node]:
        """Generic BFS. *successors=True* traverses downstream, else upstream."""
        if start not in self._g:
            return []

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        result: list[Node] = []

        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)

            if current != start and current in self._nodes:
                result.append(self._nodes[current])

            neighbors = self._g.successors(current) if successors else self._g.predecessors(current)
            for neighbor in neighbors:
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))

        return result
