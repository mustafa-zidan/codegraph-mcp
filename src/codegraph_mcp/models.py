"""Pydantic data models for structured serialization."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .enums import EdgeType, NodeType


class Node(BaseModel):
    """A single node in the code knowledge graph."""

    id: str = Field(..., description="Unique identifier, e.g. 'function:auth.loginUser'")
    type: NodeType
    name: str
    file: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    """A directed relationship between two nodes."""

    source: str = Field(..., description="Source node id")
    target: str = Field(..., description="Target node id")
    type: EdgeType


class GraphQuery(BaseModel):
    """Parameters for a graph query."""

    node_id: str
    max_depth: int = Field(default=10, ge=1, le=100)
    edge_types: list[EdgeType] | None = None


class ImpactResult(BaseModel):
    """Result of an impact analysis query."""

    source_node: str
    affected_nodes: list[Node] = Field(default_factory=list)
    affected_edges: list[Edge] = Field(default_factory=list)
    depth: int = 0


class ArchitectureSummary(BaseModel):
    """High-level architecture summary of the graph."""

    total_nodes: int = 0
    total_edges: int = 0
    node_counts: dict[str, int] = Field(default_factory=dict)
    edge_counts: dict[str, int] = Field(default_factory=dict)
    files_analyzed: int = 0
    languages: list[str] = Field(default_factory=list)
