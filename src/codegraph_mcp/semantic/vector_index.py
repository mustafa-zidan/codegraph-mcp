"""NumPy-based vector index persisted next to the Kuzu store."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from codegraph_mcp.enums import NodeType
from codegraph_mcp.models import Node

logger = logging.getLogger("codegraph_mcp.semantic.vector_index")


def vector_index_path_for_store(store_path: Path | str) -> Path:
    p = Path(store_path)
    return p.with_suffix(".vectors.npz")


def meta_path_for_store(store_path: Path | str) -> Path:
    p = Path(store_path)
    return p.with_suffix(".embeddings.json")


def node_text_for_embedding(node: Node) -> str:
    parts = [node.name, node.file or "", node.id]
    meta = node.metadata or {}
    for key in ("doc", "docstring", "comment"):
        if key in meta and meta[key]:
            parts.append(str(meta[key]))
    return "\n".join(p for p in parts if p)


def build_index(
    store_path: Path | str,
    nodes: list[Node],
    embed_fn: Any,
) -> None:
    """Compute embeddings for *nodes* and write ``*.vectors.npz`` + sidecar JSON."""
    texts = [node_text_for_embedding(n) for n in nodes]
    vectors_list = embed_fn.embed(texts)
    if len(vectors_list) != len(nodes):
        raise RuntimeError("embedding count mismatch")
    dim = len(vectors_list[0])
    mat = np.array(vectors_list, dtype=np.float32)
    out = vector_index_path_for_store(store_path)
    ids = np.array([n.id for n in nodes], dtype=object)
    np.savez_compressed(out, ids=ids, vectors=mat)
    meta = {
        "dim": dim,
        "count": len(nodes),
        "backend": str(type(embed_fn).__name__),
    }
    meta_path_for_store(store_path).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Wrote vector index %s (%d vectors, dim=%d)", out, len(nodes), dim)


def search(
    store_path: Path | str,
    query_vec: list[float],
    node_by_id: dict[str, Node],
    *,
    node_type: NodeType | None,
    limit: int,
) -> list[tuple[Node, float]]:
    """Return top *limit* nodes by cosine similarity to *query_vec*."""
    vpath = vector_index_path_for_store(store_path)
    if not vpath.is_file():
        return []
    data = np.load(vpath, allow_pickle=True)
    ids = data["ids"]
    mat = data["vectors"].astype(np.float32)
    q = np.array(query_vec, dtype=np.float32)
    qn = np.linalg.norm(q)
    if qn == 0:
        return []
    q = q / qn
    # rows normalized for cosine = dot with normalized q
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    mat_n = mat / norms
    scores = mat_n @ q
    order = np.argsort(-scores)
    out: list[tuple[Node, float]] = []
    for idx in order:
        nid = str(ids[int(idx)])
        node = node_by_id.get(nid)
        if node is None:
            continue
        if node_type and node.type != node_type:
            continue
        out.append((node, float(scores[int(idx)])))
        if len(out) >= limit:
            break
    return out
