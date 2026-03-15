"""Abstract base parser interface."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from ..models import Edge, Node

logger = logging.getLogger("codegraph_mcp.parser")


class ParseResult:
    """Container for nodes and edges extracted from a single file."""

    __slots__ = ("nodes", "edges")

    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

    def add_node(self, node: Node) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
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
