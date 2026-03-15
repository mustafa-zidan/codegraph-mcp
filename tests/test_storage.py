"""Tests for storage/sqlite_store.py."""

import tempfile
from pathlib import Path

from codegraph_mcp.enums import EdgeType, NodeType
from codegraph_mcp.models import Edge, Node
from codegraph_mcp.storage.sqlite_store import SQLiteStore


class TestSQLiteStore:
    def test_save_and_load_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "test.db")
            nodes = [
                Node(id="file:a.ts", type=NodeType.FILE, name="a.ts", language="typescript"),
                Node(id="function:greet", type=NodeType.FUNCTION, name="greet"),
            ]
            store.save_nodes(nodes)
            loaded = store.load_nodes()
            assert len(loaded) == 2
            assert {n.id for n in loaded} == {"file:a.ts", "function:greet"}
            store.close()

    def test_save_and_load_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "test.db")
            edges = [
                Edge(source="file:a.ts", target="function:greet", type=EdgeType.DEFINES),
            ]
            store.save_edges(edges)
            loaded = store.load_edges()
            assert len(loaded) == 1
            assert loaded[0].source == "file:a.ts"
            store.close()

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "test.db")
            store.save_nodes([Node(id="x", type=NodeType.FILE, name="x")])
            store.clear()
            assert store.load_nodes() == []
            store.close()
