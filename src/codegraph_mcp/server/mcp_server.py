"""MCP server exposing CodeGraph tools to AI agents."""

from __future__ import annotations

import json
import logging
import os
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
_graph_ui_routes_registered: bool = False

mcp = FastMCP("CodeGraph MCP", host="0.0.0.0", port=int(os.environ.get("FASTMCP_PORT", os.environ.get("PORT", "8080"))))

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})


def _register_graph_ui_routes() -> None:
    """Register /api/graph and /graph (vis-network). Idempotent."""
    global _graph_ui_routes_registered
    if _graph_ui_routes_registered:
        return
    _graph_ui_routes_registered = True

    from starlette.responses import HTMLResponse, JSONResponse
    from starlette.requests import Request

    def _graph_payload(limit: int) -> dict:
        if _builder is None:
            return {"nodes": [], "edges": [], "truncated": False, "error": "graph not initialized"}
        nodes_all = _builder.all_nodes()
        truncated = len(nodes_all) > limit
        if truncated:
            nodes_all = nodes_all[:limit]
        allowed = {n.id for n in nodes_all}
        nodes_out = [
            {"id": n.id, "label": n.name, "group": n.type.value}
            for n in nodes_all
        ]
        edges_out: list[dict] = []
        for e in _builder.all_edges():
            if e.source in allowed and e.target in allowed:
                edges_out.append({
                    "from": e.source,
                    "to": e.target,
                    "title": e.type.value,
                })
        return {"nodes": nodes_out, "edges": edges_out, "truncated": truncated}

    @mcp.custom_route("/api/graph", methods=["GET"])
    async def graph_api(request: Request) -> JSONResponse:
        raw = request.query_params.get("limit", "500")
        try:
            limit = max(1, min(int(raw), 50_000))
        except ValueError:
            limit = 500
        return JSONResponse(_graph_payload(limit))

    @mcp.custom_route("/graph", methods=["GET"])
    async def graph_page(request: Request) -> HTMLResponse:
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>CodeGraph</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #0f1419; color: #e6edf3; }
    #header { padding: 10px 16px; border-bottom: 1px solid #30363d; }
    #net { width: 100vw; height: calc(100vh - 52px); background: #0d1117; }
    a { color: #58a6ff; }
  </style>
</head>
<body>
  <div id="header">CodeGraph <span id="meta"></span> &middot; <a href="/api/graph">JSON</a></div>
  <div id="net"></div>
  <script>
    const q = new URLSearchParams(location.search);
    const lim = q.get("limit") || "500";
    fetch("/api/graph?limit=" + encodeURIComponent(lim))
      .then(r => r.json())
      .then(data => {
        document.getElementById("meta").textContent =
          (data.nodes && data.nodes.length) + " nodes, " + (data.edges && data.edges.length) + " edges"
          + (data.truncated ? " (truncated)" : "");
        const nodes = new vis.DataSet((data.nodes || []).map(n => ({
          id: n.id, label: n.label, group: n.group
        })));
        const edges = new vis.DataSet((data.edges || []).map((e, i) => ({
          id: "e" + i, from: e.from, to: e.to, title: e.title || ""
        })));
        const container = document.getElementById("net");
        new vis.Network(container, { nodes, edges }, {
          physics: { enabled: true, stabilization: { iterations: 80 } },
          nodes: { shape: "dot", size: 10, font: { color: "#e6edf3", size: 11 } },
          edges: { arrows: "to", smooth: { type: "continuous" } },
          groups: {
            file: { color: "#388bfd" },
            function: { color: "#3fb950" },
            class: { color: "#d29922" },
            module: { color: "#a371f7" },
            repository: { color: "#f85149" },
            default: { color: "#8b949e" }
          }
        });
      })
      .catch(err => {
        document.getElementById("meta").textContent = "load error: " + err;
      });
  </script>
</body>
</html>"""
        return HTMLResponse(html)


def initialize(repo_path: str, db_path: str = "codegraph.db", *, graph_ui: bool = False) -> None:
    """Build (or reload) the graph for *repo_path*.

    If a SQLite database already exists at *db_path*, the graph is loaded
    from it instead of re-scanning the repository — making cold starts
    near-instant for previously analyzed repos.
    """
    global _builder, _engine, _store

    setup_logging()
    logger.info("Initializing CodeGraph for %s", repo_path)

    _store = SQLiteStore(db_path)
    _builder = GraphBuilder()

    db_file = Path(db_path)
    if db_file.exists() and db_file.stat().st_size > 0:
        # ---------- fast path: load from SQLite ----------
        logger.info("Found existing graph database — loading from %s", db_path)
        nodes = _store.load_nodes()
        edges = _store.load_edges()
        if nodes:
            from ..models import Edge, Node
            from ..parser.base import ParseResult

            result = ParseResult()
            result.nodes = nodes
            result.edges = edges
            _builder.add_parse_result(result)
            logger.info(
                "Loaded graph from SQLite: %d nodes, %d edges",
                len(nodes), len(edges),
            )
        else:
            # DB exists but is empty — fall through to full build
            _full_build(repo_path)
    else:
        # ---------- cold path: full repo scan ----------
        _full_build(repo_path)

    _engine = QueryEngine(_builder.graph, _builder._node_index)
    logger.info("CodeGraph ready.")

    if graph_ui:
        _register_graph_ui_routes()


def _full_build(repo_path: str) -> None:
    """Scan, parse, and persist the graph."""
    repo = Path(repo_path).resolve()
    _builder.build_from_repository(repo)
    _store.save_nodes(_builder.all_nodes())
    _store.save_edges(_builder.all_edges())


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
