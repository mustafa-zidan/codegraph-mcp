"""SQLite persistence for the code knowledge graph."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from codegraph_mcp.enums import EdgeType, NodeType
from codegraph_mcp.models import Edge, Node

logger = logging.getLogger("codegraph_mcp.storage")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id   TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    file TEXT,
    language TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    type   TEXT NOT NULL,
    PRIMARY KEY (source, target, type)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
"""


class SQLiteStore:
    """Read/write graph data to a local SQLite database."""

    def __init__(self, db_path: Path | str = "codegraph.db") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.executescript(_SCHEMA)
        logger.info("SQLite store ready: %s", self._db_path)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_nodes(self, nodes: list[Node]) -> None:
        """Upsert a batch of nodes."""
        self._conn.executemany(
            "INSERT OR REPLACE INTO nodes (id, type, name, file, language, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            [(n.id, n.type.value, n.name, n.file, n.language, json.dumps(n.metadata)) for n in nodes],
        )
        self._conn.commit()
        logger.info("Saved %d nodes", len(nodes))

    def save_edges(self, edges: list[Edge]) -> None:
        """Upsert a batch of edges."""
        self._conn.executemany(
            "INSERT OR REPLACE INTO edges (source, target, type) VALUES (?, ?, ?)",
            [(e.source, e.target, e.type.value) for e in edges],
        )
        self._conn.commit()
        logger.info("Saved %d edges", len(edges))

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load_nodes(self) -> list[Node]:
        """Load all nodes from the database."""
        rows = self._conn.execute("SELECT id, type, name, file, language, metadata FROM nodes").fetchall()
        return [
            Node(
                id=r[0],
                type=NodeType(r[1]),
                name=r[2],
                file=r[3],
                language=r[4],
                metadata=json.loads(r[5]) if r[5] else {},
            )
            for r in rows
        ]

    def load_edges(self) -> list[Edge]:
        """Load all edges from the database."""
        rows = self._conn.execute("SELECT source, target, type FROM edges").fetchall()
        return [Edge(source=r[0], target=r[1], type=EdgeType(r[2])) for r in rows]

    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all data."""
        self._conn.executescript("DELETE FROM edges; DELETE FROM nodes;")
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()
