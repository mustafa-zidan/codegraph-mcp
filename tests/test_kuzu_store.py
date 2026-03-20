"""Tests for storage/kuzu_store.py."""

from pathlib import Path

from codegraph_mcp.enums import EdgeType, NodeType
from codegraph_mcp.models import Edge, Node
from codegraph_mcp.storage.kuzu_store import KuzuStore


class TestKuzuStore:
    def test_save_and_load_nodes(self, tmp_path: Path) -> None:
        db = tmp_path / "cg.kuzu"
        store = KuzuStore(db)
        nodes = [
            Node(id="f:a", type=NodeType.FILE, name="a", file="a.ts", language="typescript", metadata={}),
            Node(id="function:a.b", type=NodeType.FUNCTION, name="b", file="a.ts", language="typescript", metadata={}),
        ]
        store.save_graph(nodes, [Edge(source="f:a", target="function:a.b", type=EdgeType.DEFINES)])
        loaded = store.load_nodes()
        assert len(loaded) == 2
        by_id = {n.id: n for n in loaded}
        assert by_id["f:a"].name == "a"
        store.close()

    def test_clear(self, tmp_path: Path) -> None:
        db = tmp_path / "cg.kuzu"
        store = KuzuStore(db)
        store.save_graph(
            [Node(id="x", type=NodeType.FILE, name="x", file="x.ts", language="ts", metadata={})],
            [],
        )
        store.clear()
        assert store.load_nodes() == []
        store.close()

    def test_search_nodes_fts(self, tmp_path: Path) -> None:
        db = tmp_path / "cg.kuzu"
        store = KuzuStore(db)
        n = Node(id="function:x.y", type=NodeType.FUNCTION, name="helloWorld", file="f.ts", language="ts", metadata={})
        store.save_graph([n], [])
        idx = {n.id: n}
        hits = store.search_nodes_fts("helloWorld", None, 10, idx)
        assert len(hits) >= 1
        assert hits[0].id == "function:x.y"
        store.close()
