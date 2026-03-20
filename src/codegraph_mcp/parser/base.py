"""Abstract base parser interface."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from tree_sitter import Node as TSNode

from codegraph_mcp.models import Edge, Node

logger = logging.getLogger("codegraph_mcp.parser")


def utf8_node_text(node: TSNode) -> str:
    """Return UTF-8 text for a tree-sitter node, or empty string if absent."""
    raw = node.text
    if raw is None:
        return ""
    return raw.decode("utf-8")


class ParseResult:
    """Container for nodes and edges extracted from a single file."""

    __slots__ = ("nodes", "edges")

    def __init__(self) -> None:
        """Create empty node and edge lists."""
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

    def add_node(self, node: Node) -> None:
        """Append *node* to the result list."""
        self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
        """Append *edge* to the result list."""
        self.edges.append(edge)


class BaseParser(ABC):
    """Interface every language parser must implement."""

    language: str  # e.g. "typescript"

    @abstractmethod
    def parse_file(self, path: Path, source: bytes) -> ParseResult:
        """Parse *source* and return extracted nodes and edges.

        Implementations must catch internal errors and return a
        partial ``ParseResult`` rather than raising.
        """

    # ------- helpers available to subclasses ------

    @staticmethod
    def _make_id(kind: str, *parts: str) -> str:
        """Build a deterministic node id, e.g. ``function:auth.login``."""
        return f"{kind}:{'.'.join(parts)}"
