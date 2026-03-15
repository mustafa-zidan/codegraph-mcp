"""MCP server exposing CodeGraph tools to AI agents."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..enums import NodeType
from ..graph.builder import GraphBuilder
from ..graph.query_engine import QueryEngine
from ..models import GraphQuery
from ..storage.sqlite_store import SQLiteStore
from ..logging_config import setup_logging

logger = logging.getLogger("codegraph_mcp.server")

# ---------------------------------------------------------------------------
# Global state (populated by `initialize`)
# ---------------------------------------------------------------------------
_builder: GraphBuilder | None = None
_engine: QueryEngine | None = None
_store: SQLiteStore | None = None

mcp = FastMCP("CodeGraph MCP")


def initialize(repo_path: str, db_path: str = "codegraph.db") -> None:
    """Build (or reload) the graph for *repo_path*."""
    global _builder, _engine, _store

    setup_logging()
    logger.info("Initializing CodeGraph for %s", repo_path)

    _store = SQLiteStore(db_path)
    _builder = GraphBuilder()

    repo = Path(repo_path).resolve()
    _builder.build_from_repository(repo)

    # Persist
    _store.save_nodes(_builder.all_nodes())
    _store.save_edges(_builder.all_edges())

    _engine = QueryEngine(_builder.graph, _builder._node_index)
    logger.info("CodeGraph ready.")


def _require_engine() -> QueryEngine:
    if _engine is None:
        raise RuntimeError("CodeGraph not initialized. Call `initialize(repo_path)` first.")
    return _engine


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_nodes(query: str, node_type: str | None = None, limit: int = 50) -> str:
    """Search for nodes by name or type."""
    engine = _require_engine()
    nt = NodeType(node_type) if node_type else None
    nodes = engine.search_nodes(query, node_type=nt, limit=limit)
    return json.dumps([n.model_dump() for n in nodes], default=str)


@mcp.tool()
def trace_dependencies(node_id: str, max_depth: int = 10) -> str:
    """Trace downstream dependencies of a node."""
    engine = _require_engine()
    gq = GraphQuery(node_id=node_id, max_depth=max_depth)
    nodes = engine.trace_dependencies(gq)
    return json.dumps([n.model_dump() for n in nodes], default=str)


@mcp.tool()
def trace_dependents(node_id: str, max_depth: int = 10) -> str:
    """Trace upstream dependents of a node — what depends on this?"""
    engine = _require_engine()
    gq = GraphQuery(node_id=node_id, max_depth=max_depth)
    nodes = engine.trace_dependents(gq)
    return json.dumps([n.model_dump() for n in nodes], default=str)


@mcp.tool()
def impact_analysis(node_id: str, max_depth: int = 10) -> str:
    """Full impact analysis — what breaks if this node changes?"""
    engine = _require_engine()
    gq = GraphQuery(node_id=node_id, max_depth=max_depth)
    result = engine.impact_analysis(gq)
    return result.model_dump_json()


@mcp.tool()
def trace_path(source_id: str, target_id: str) -> str:
    """Shortest path between two nodes."""
    engine = _require_engine()
    nodes = engine.trace_path(source_id, target_id)
    return json.dumps([n.model_dump() for n in nodes], default=str)


@mcp.tool()
def architecture_summary() -> str:
    """High-level summary of the codebase graph."""
    engine = _require_engine()
    summary = engine.architecture_summary()
    return summary.model_dump_json()
