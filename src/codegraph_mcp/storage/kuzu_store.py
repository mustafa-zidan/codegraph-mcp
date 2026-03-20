"""Kuzu persistence and full-text search for the code knowledge graph."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import kuzu

from codegraph_mcp.enums import EdgeType, NodeType
from codegraph_mcp.models import Edge, Node

logger = logging.getLogger("codegraph_mcp.storage")

_NODE_TABLE = "CodeNode"
_REL_TABLE = "CODE_EDGE"
_FTS_INDEX = "code_node_fts"


def _cypher_quote(s: str | None) -> str:
    """Escape a string for single-quoted Cypher literals."""
    if s is None:
        return "NULL"
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


class KuzuStore:
    """Read/write graph data to a local Kuzu database with FTS on node text fields."""

    def __init__(self, db_path: Path | str = "codegraph.kuzu") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(self._db_path))
        self._conn = kuzu.Connection(self._db)
        self._fts_ready = False
        self._ensure_schema()
        logger.info("Kuzu store ready: %s", self._db_path)

    def _run_query(self, query: str) -> Any:
        """Execute Cypher; return type is driver-specific (``QueryResult``)."""
        return self._conn.execute(query)

    def _ensure_schema(self) -> None:
        self._conn.execute(
            f"""
            CREATE NODE TABLE IF NOT EXISTS {_NODE_TABLE} (
                id STRING,
                type STRING,
                name STRING,
                file STRING,
                language STRING,
                metadata STRING,
                PRIMARY KEY (id)
            )
            """
        )
        self._conn.execute(
            f"""
            CREATE REL TABLE IF NOT EXISTS {_REL_TABLE} (
                FROM {_NODE_TABLE} TO {_NODE_TABLE},
                rel_type STRING
            )
            """
        )
        self._conn.execute("INSTALL FTS")
        self._conn.execute("LOAD EXTENSION FTS")
        try:
            self._conn.execute(f"CALL CREATE_FTS_INDEX('{_NODE_TABLE}', '{_FTS_INDEX}', ['name', 'file', 'id'])")
            self._fts_ready = True
        except Exception as e:
            err = str(e).lower()
            if "already exists" in err:
                self._fts_ready = True
            else:
                logger.warning("FTS index creation skipped or failed: %s", e)
                self._fts_ready = False

    def _clear_graph_data(self) -> None:
        self._conn.execute(f"MATCH (a:{_NODE_TABLE})-[e:{_REL_TABLE}]->(b:{_NODE_TABLE}) DELETE e")
        self._conn.execute(f"MATCH (c:{_NODE_TABLE}) DELETE c")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_nodes(self, nodes: list[Node]) -> None:
        """Replace all nodes (and clear edges first if re-saving)."""
        self._clear_graph_data()
        for n in nodes:
            meta = json.dumps(n.metadata)
            file_q = _cypher_quote(n.file)
            lang_q = _cypher_quote(n.language)
            self._conn.execute(
                f"""
                CREATE (c:{_NODE_TABLE} {{
                    id: {_cypher_quote(n.id)},
                    type: {_cypher_quote(n.type.value)},
                    name: {_cypher_quote(n.name)},
                    file: {file_q},
                    language: {lang_q},
                    metadata: {_cypher_quote(meta)}
                }})
                """
            )
        logger.info("Saved %d nodes", len(nodes))

    def save_edges(self, edges: list[Edge]) -> None:
        """Insert edges (nodes must already exist)."""
        for e in edges:
            self._conn.execute(
                f"""
                MATCH (a:{_NODE_TABLE} {{id: {_cypher_quote(e.source)}}}),
                      (b:{_NODE_TABLE} {{id: {_cypher_quote(e.target)}}})
                CREATE (a)-[:{_REL_TABLE} {{rel_type: {_cypher_quote(e.type.value)}}}]->(b)
                """
            )
        logger.info("Saved %d edges", len(edges))

    def save_graph(self, nodes: list[Node], edges: list[Edge]) -> None:
        """Clear and persist nodes then edges in one logical operation."""
        self.save_nodes(nodes)
        self.save_edges(edges)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load_nodes(self) -> list[Node]:
        """Load all nodes from the database."""
        q = f"MATCH (c:{_NODE_TABLE}) RETURN c.id, c.type, c.name, c.file, c.language, c.metadata"
        result = self._run_query(q)
        rows: list[Node] = []
        while result.has_next():
            r: Any = result.get_next()
            rows.append(
                Node(
                    id=r[0],
                    type=NodeType(r[1]),
                    name=r[2],
                    file=r[3],
                    language=r[4],
                    metadata=json.loads(r[5]) if r[5] else {},
                )
            )
        return rows

    def load_edges(self) -> list[Edge]:
        """Load all edges from the database."""
        result = self._run_query(
            f"MATCH (a:{_NODE_TABLE})-[e:{_REL_TABLE}]->(b:{_NODE_TABLE}) RETURN a.id, b.id, e.rel_type"
        )
        rows: list[Edge] = []
        while result.has_next():
            r: Any = result.get_next()
            rows.append(Edge(source=r[0], target=r[1], type=EdgeType(r[2])))
        return rows

    def node_count(self) -> int:
        result = self._run_query(f"MATCH (c:{_NODE_TABLE}) RETURN COUNT(*)")
        if result.has_next():
            row: Any = result.get_next()
            return int(row[0])
        return 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_fts_query(q: str) -> str:
        """Reduce FTS syntax breakage; keep alphanumerics and spaces."""
        q = q.strip()
        if not q:
            return ""
        # Collapse whitespace; strip characters that often break MATCH
        q = re.sub(r"\s+", " ", q)
        return q

    def search_nodes_fts(
        self,
        query: str,
        node_type: NodeType | None,
        limit: int,
        node_by_id: dict[str, Node],
    ) -> list[Node]:
        """BM25-ranked FTS over name, file, id; filter by type; cap *limit*."""
        q = self._sanitize_fts_query(query)
        if not q or not self._fts_ready:
            return []

        try:
            result = self._run_query(
                f"CALL QUERY_FTS_INDEX('{_NODE_TABLE}', '{_FTS_INDEX}', {_cypher_quote(q)}) RETURN *"
            )
        except Exception as e:
            logger.info("FTS query failed, will fall back: %s", e)
            return []

        ranked: list[tuple[float, str]] = []
        while result.has_next():
            row: Any = result.get_next()
            # row: [node_struct, score] or similar
            if len(row) < 2:
                continue
            node_data, score = row[0], row[1]
            if isinstance(node_data, dict) and "id" in node_data:
                nid = str(node_data["id"])
            else:
                continue
            try:
                sc = float(score)
            except (TypeError, ValueError):
                sc = 0.0
            ranked.append((sc, nid))

        ranked.sort(key=lambda x: -x[0])
        out: list[Node] = []
        for _, nid in ranked:
            node = node_by_id.get(nid)
            if node is None:
                continue
            if node_type and node.type != node_type:
                continue
            out.append(node)
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all nodes and edges."""
        self._clear_graph_data()
        logger.info("Kuzu store cleared")

    def close(self) -> None:
        """Close connection and release resources."""
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = None  # type: ignore[assignment]
        self._db = None  # type: ignore[assignment]
