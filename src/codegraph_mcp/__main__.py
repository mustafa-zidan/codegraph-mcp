"""CLI entry-point for CodeGraph MCP.

Usage:
    python -m codegraph_mcp analyze ./my_repo
    python -m codegraph_mcp serve  ./my_repo
    python -m codegraph_mcp serve  ./my_repo --transport sse --port 8080
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .logging_config import setup_logging
from .graph.builder import GraphBuilder
from .graph.query_engine import QueryEngine
from .storage.sqlite_store import SQLiteStore


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="codegraph-mcp",
        description="Build and query a knowledge graph of your codebase.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- analyze ----
    p_analyze = sub.add_parser("analyze", help="Analyze a repository and print summary")
    p_analyze.add_argument("repo", type=Path, nargs="?",
                           default=Path(os.environ.get("REPO_PATH", ".")),
                           help="Path to the repository root")
    p_analyze.add_argument("--db", type=str, default="codegraph.db",
                           help="SQLite database path")

    # ---- serve ----
    p_serve = sub.add_parser("serve", help="Start the MCP server")
    p_serve.add_argument("repo", type=Path, nargs="?",
                         default=Path(os.environ.get("REPO_PATH", ".")),
                         help="Path to the repository root")
    p_serve.add_argument("--db", type=str, default="codegraph.db",
                         help="SQLite database path")
    p_serve.add_argument("--transport", type=str,
                         default=os.environ.get("MCP_TRANSPORT", "stdio"),
                         choices=["stdio", "sse", "streamable-http"],
                         help="MCP transport: stdio (local), sse, or streamable-http (remote)")
    p_serve.add_argument("--port", type=int,
                         default=int(os.environ.get("PORT", "8080")),
                         help="Port for SSE transport")

    args = parser.parse_args(argv)

    if args.command == "analyze":
        _run_analyze(args.repo, args.db)
    elif args.command == "serve":
        _run_serve(args.repo, args.db, args.transport, args.port)


def _run_analyze(repo: Path, db_path: str) -> None:
    builder = GraphBuilder()
    builder.build_from_repository(repo.resolve())

    store = SQLiteStore(db_path)
    store.save_nodes(builder.all_nodes())
    store.save_edges(builder.all_edges())
    store.close()

    engine = QueryEngine(builder.graph, builder._node_index)
    summary = engine.architecture_summary()
    print(json.dumps(summary.model_dump(), indent=2))


def _run_serve(repo: Path, db_path: str, transport: str, port: int) -> None:
    from .server.mcp_server import initialize, mcp

    # Build or load the graph
    initialize(str(repo), db_path)

    os.environ["PORT"] = str(port)
    os.environ["FASTMCP_PORT"] = str(port)

    # Let FastMCP handle server startup
    mcp.run(transport=transport)
