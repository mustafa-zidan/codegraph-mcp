"""MCP server exposing CodeGraph tools to AI agents."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from codegraph_mcp.enums import NodeType
from codegraph_mcp.graph.builder import GraphBuilder
from codegraph_mcp.graph.query_engine import QueryEngine
from codegraph_mcp.logging_config import setup_logging
from codegraph_mcp.models import GraphQuery
from codegraph_mcp.storage.kuzu_store import KuzuStore

logger = logging.getLogger("codegraph_mcp.server")

# Default HTTP port when PORT / FASTMCP_PORT are unset (avoid 8080 / 3000 collisions).
DEFAULT_HTTP_PORT = 3847

# ---------------------------------------------------------------------------
# Global state (populated by `initialize`)
# ---------------------------------------------------------------------------
_builder: GraphBuilder | None = None
_engine: QueryEngine | None = None
_store: KuzuStore | None = None
_store_path: str | None = None
_graph_ui_routes_registered: bool = False

mcp = FastMCP(
    "CodeGraph MCP",
    host="0.0.0.0",
    port=int(os.environ.get("FASTMCP_PORT", os.environ.get("PORT", str(DEFAULT_HTTP_PORT)))),
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _register_graph_ui_routes() -> None:
    """Register /api/graph and /graph (vis-network). Idempotent."""
    global _graph_ui_routes_registered
    if _graph_ui_routes_registered:
        return
    _graph_ui_routes_registered = True

    def _graph_payload(limit: int) -> dict[str, Any]:
        if _builder is None:
            return {"nodes": [], "edges": [], "truncated": False, "error": "graph not initialized"}
        # Edges often connect a parsed node to a *stub* (endpoint added only in NetworkX for consistency).
        # The old filter required both ends in all_nodes(), which dropped every edge touching a stub.
        all_edges = _builder.all_edges()
        max_nodes = max(1, min(int(limit), 50_000))
        max_edges = max(500, min(max_nodes * 4, 20_000))

        claimed: dict[str, dict[str, str]] = {}
        edges_out: list[dict] = []

        def ensure(nid: str) -> bool:
            if nid in claimed:
                return True
            if len(claimed) >= max_nodes:
                return False
            node = _builder.get_node(nid)
            if node:
                claimed[nid] = {"id": node.id, "label": node.name, "group": node.type.value}
            else:
                claimed[nid] = {"id": nid, "label": nid, "group": "default"}
            return True

        truncated = False
        for e in all_edges:
            if len(edges_out) >= max_edges:
                truncated = True
                break
            if not ensure(e.source) or not ensure(e.target):
                truncated = True
                break
            edges_out.append({"from": e.source, "to": e.target, "title": e.type.value})

        nodes_out = list(claimed.values())
        if len(edges_out) < len(all_edges):
            truncated = True
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


def initialize(repo_path: str, store_path: str | None = None, *, graph_ui: bool = False) -> None:
    """Build (or reload) the graph for *repo_path*.

    If a Kuzu database already exists at *store_path* with at least one node,
    the graph is loaded from it instead of re-scanning the repository.
    """
    global _builder, _engine, _store, _store_path

    setup_logging()
    logger.info("Initializing CodeGraph for %s", repo_path)

    resolved = Path(store_path or os.environ.get("CODEGRAPH_STORE") or "codegraph.kuzu").resolve()
    _store_path = str(resolved)
    _store = KuzuStore(_store_path)
    _builder = GraphBuilder()

    if _store.node_count() > 0:
        # ---------- fast path: load from Kuzu ----------
        logger.info("Found existing graph store — loading from %s", _store_path)
        nodes = _store.load_nodes()
        edges = _store.load_edges()
        if nodes:
            from codegraph_mcp.parser.base import ParseResult

            result = ParseResult()
            result.nodes = nodes
            result.edges = edges
            _builder.add_parse_result(result)
            logger.info(
                "Loaded graph from Kuzu: %d nodes, %d edges",
                len(nodes),
                len(edges),
            )
        else:
            logger.info(
                "Graph store empty — scanning repository (large trees can take several minutes; "
                "run `codegraph-mcp analyze` first for a faster cold start)."
            )
            _full_build(repo_path)
    else:
        # ---------- cold path: full repo scan ----------
        logger.info(
            "No graph store yet — scanning repository (large trees can take several minutes; "
            "run `codegraph-mcp analyze` first for a faster cold start)."
        )
        _full_build(repo_path)

    _engine = QueryEngine(_builder.graph, _builder._node_index, fts_store=_store)
    logger.info("CodeGraph ready.")

    if graph_ui:
        _register_graph_ui_routes()


def _full_build(repo_path: str) -> None:
    """Scan *repo_path*, build the graph, and write nodes and edges to Kuzu.

    Expects global ``_builder`` and ``_store`` to be set by ``initialize``.
    """
    global _builder, _store
    assert _builder is not None
    assert _store is not None
    builder, store = _builder, _store
    repo = Path(repo_path).resolve()
    builder.build_from_repository(repo)
    store.save_graph(builder.all_nodes(), builder.all_edges())
    if _store_path is not None:
        from codegraph_mcp.semantic.build import maybe_build_semantic_index

        maybe_build_semantic_index(_store_path, builder.all_nodes())


def _require_engine() -> QueryEngine:
    """Return the shared query engine or raise if ``initialize`` has not run."""
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


@mcp.tool()
def search_nodes_semantic(query: str, node_type: str | None = None, limit: int = 20) -> str:
    """Semantic search over nodes using the optional vector index (cosine similarity).

    Requires ``pip install codegraph-mcp[semantic]``, a built index (see README),
    and embedding configuration (local model or OpenAI-compatible API).
    """
    engine = _require_engine()
    if _store_path is None:
        return json.dumps([])
    try:
        from codegraph_mcp.semantic.embeddings import describe_embedding_backend, get_backend_from_env
        from codegraph_mcp.semantic.vector_index import search as semantic_search
        from codegraph_mcp.semantic.vector_index import vector_index_path_for_store
    except ImportError as e:
        return json.dumps(
            {"error": "semantic extra not installed", "hint": "pip install codegraph-mcp[semantic]", "detail": str(e)}
        )
    vpath = vector_index_path_for_store(_store_path)
    if not vpath.is_file():
        return json.dumps(
            {
                "error": "no vector index",
                "hint": "Set CODEGRAPH_BUILD_SEMANTIC_INDEX=1 and re-analyze, or run analyze with semantic index build",
            }
        )
    nt = NodeType(node_type) if node_type else None
    backend = get_backend_from_env()
    logger.info("search_nodes_semantic: embedding query via %s", describe_embedding_backend(backend))
    qvec = backend.embed([query])[0]
    pairs = semantic_search(
        _store_path,
        qvec,
        engine.node_index,
        node_type=nt,
        limit=limit,
    )
    out = []
    for node, score in pairs:
        d = node.model_dump()
        d["_score"] = score
        out.append(d)
    return json.dumps(out, default=str)
