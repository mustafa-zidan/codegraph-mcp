"""CLI entry-point for CodeGraph MCP.

Usage:
    python -m codegraph_mcp analyze ./my_repo
    python -m codegraph_mcp serve  ./my_repo
    python -m codegraph_mcp serve  ./my_repo --transport sse --port 3847
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Literal, cast

from codegraph_mcp.graph.builder import GraphBuilder
from codegraph_mcp.graph.query_engine import QueryEngine
from codegraph_mcp.logging_config import setup_logging
from codegraph_mcp.storage.kuzu_store import KuzuStore


def _default_store_path() -> str:
    return os.environ.get("CODEGRAPH_STORE") or "codegraph.kuzu"


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="codegraph-mcp",
        description="Build and query a knowledge graph of your codebase.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- analyze ----
    p_analyze = sub.add_parser("analyze", help="Analyze a repository and print summary")
    p_analyze.add_argument(
        "repo", type=Path, nargs="?", default=Path(os.environ.get("REPO_PATH", ".")), help="Path to the repository root"
    )
    p_analyze.add_argument(
        "--store",
        type=str,
        default=_default_store_path(),
        help="Kuzu database path (default: codegraph.kuzu or CODEGRAPH_STORE)",
    )
    p_analyze.add_argument(
        "--semantic-index",
        action="store_true",
        help="Build embedding vector index (requires pip install codegraph-mcp[semantic])",
    )

    # ---- serve ----
    p_serve = sub.add_parser("serve", help="Start the MCP server")
    p_serve.add_argument(
        "repo", type=Path, nargs="?", default=Path(os.environ.get("REPO_PATH", ".")), help="Path to the repository root"
    )
    p_serve.add_argument(
        "--store",
        type=str,
        default=_default_store_path(),
        help="Kuzu database path (default: codegraph.kuzu or CODEGRAPH_STORE)",
    )
    p_serve.add_argument(
        "--transport",
        type=str,
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        choices=["stdio", "sse", "streamable-http"],
        help="MCP transport: stdio (local), sse, or streamable-http (remote)",
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "3847")),
        help="Port for HTTP transports (default 3847, or PORT env)",
    )
    p_serve.add_argument(
        "--graph-ui",
        action="store_true",
        help="Expose GET /graph and /api/graph (HTTP transports only; not stdio)",
    )

    args = parser.parse_args(argv)

    if args.command == "analyze":
        _run_analyze(args.repo, args.store, semantic_index=args.semantic_index)
    elif args.command == "serve":
        graph_ui_flag = args.graph_ui or os.environ.get("GRAPH_UI", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        _run_serve(args.repo, args.store, args.transport, args.port, graph_ui=graph_ui_flag)


def _run_analyze(repo: Path, store_path: str, *, semantic_index: bool = False) -> None:
    if semantic_index:
        os.environ["CODEGRAPH_BUILD_SEMANTIC_INDEX"] = "1"

    builder = GraphBuilder()
    builder.build_from_repository(repo.resolve())

    resolved = str(Path(store_path).resolve())
    store = KuzuStore(resolved)
    store.save_graph(builder.all_nodes(), builder.all_edges())

    from codegraph_mcp.semantic.build import maybe_build_semantic_index

    maybe_build_semantic_index(resolved, builder.all_nodes())

    engine = QueryEngine(builder.graph, builder._node_index, fts_store=store)
    summary = engine.architecture_summary()
    store.close()
    print(json.dumps(summary.model_dump(), indent=2))


def _run_serve(
    repo: Path,
    store_path: str,
    transport: str,
    port: int,
    *,
    graph_ui: bool = False,
) -> None:
    # FastMCP binds ``self.settings.port`` from values captured when ``mcp`` is constructed
    # (import time). Set these *before* importing ``mcp_server`` so ``--port`` is honored.
    os.environ["PORT"] = str(port)
    os.environ["FASTMCP_PORT"] = str(port)

    from codegraph_mcp.server.mcp_server import initialize, mcp

    log = logging.getLogger("codegraph_mcp")
    graph_ui_effective = graph_ui and transport != "stdio"
    if graph_ui and transport == "stdio":
        log.warning(
            "--graph-ui is ignored for stdio transport (no HTTP server). "
            "Use --transport sse or streamable-http to enable /graph.",
        )

    # Build or load the graph
    initialize(str(repo), store_path, graph_ui=graph_ui_effective)

    # Let FastMCP handle server startup
    mcp.run(transport=cast(Literal["stdio", "sse", "streamable-http"], transport))
