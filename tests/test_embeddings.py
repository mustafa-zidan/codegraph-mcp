"""Tests for OpenAI-compatible embedding client batching."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from codegraph_mcp.semantic.embeddings import OpenAICompatibleEmbeddings


def _fake_items(count: int, dim: int = 3) -> list[dict]:
    return [{"index": i, "embedding": [float(i), 0.0, float(dim)]} for i in range(count)]


def test_embed_batches_matching_response():
    emb = OpenAICompatibleEmbeddings(
        base_url="http://test/v1",
        api_key="",
        model="m",
        batch_size=4,
    )

    calls: list[int] = []

    def fake_post(url: str, headers: dict, body: dict, timeout: float = 120.0):
        inp = body["input"]
        calls.append(len(inp))
        return {"data": _fake_items(len(inp))}

    with patch("codegraph_mcp.semantic.embeddings._post_json", side_effect=fake_post):
        out = emb.embed(["a", "b", "c", "c", "d"])

    assert len(out) == 5
    assert calls == [4, 1]


def test_embed_falls_back_when_batch_returns_fewer_vectors():
    emb = OpenAICompatibleEmbeddings(
        base_url="http://test/v1",
        api_key="",
        model="m",
        batch_size=8,
    )

    def fake_post(url: str, headers: dict, body: dict, timeout: float = 120.0):
        n = len(body["input"])
        if n > 1:
            return {"data": _fake_items(1)}
        return {"data": _fake_items(1)}

    texts = ["x"] * 5
    with patch("codegraph_mcp.semantic.embeddings._post_json", side_effect=fake_post):
        out = emb.embed(texts)

    assert len(out) == 5
    assert emb._single_only is True


def test_embed_single_input_mismatch_raises():
    emb = OpenAICompatibleEmbeddings(
        base_url="http://test/v1",
        api_key="",
        model="m",
        batch_size=64,
    )

    def fake_post(url: str, headers: dict, body: dict, timeout: float = 120.0):
        return {"data": []}

    with patch("codegraph_mcp.semantic.embeddings._post_json", side_effect=fake_post):
        with pytest.raises(RuntimeError, match="1 input"):
            emb.embed(["only"])
