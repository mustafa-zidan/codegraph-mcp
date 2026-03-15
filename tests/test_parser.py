"""Tests for parser layer."""

from pathlib import Path

from codegraph_mcp.parser.typescript import TypeScriptParser
from codegraph_mcp.parser.java import JavaParser
from codegraph_mcp.enums import NodeType, EdgeType


class TestTypeScriptParser:
    def test_extracts_function(self, sample_ts_source: bytes):
        parser = TypeScriptParser()
        result = parser.parse_file(Path("test.ts"), sample_ts_source)
        func_nodes = [n for n in result.nodes if n.type == NodeType.FUNCTION]
        assert any(n.name == "greet" for n in func_nodes)

    def test_extracts_import(self, sample_ts_source: bytes):
        parser = TypeScriptParser()
        result = parser.parse_file(Path("test.ts"), sample_ts_source)
        import_edges = [e for e in result.edges if e.type == EdgeType.IMPORTS]
        assert len(import_edges) >= 1

    def test_extracts_class(self, sample_ts_source: bytes):
        parser = TypeScriptParser()
        result = parser.parse_file(Path("test.ts"), sample_ts_source)
        class_nodes = [n for n in result.nodes if n.type == NodeType.CLASS]
        assert any(n.name == "Greeter" for n in class_nodes)

    def test_handles_empty_source(self):
        parser = TypeScriptParser()
        result = parser.parse_file(Path("empty.ts"), b"")
        assert len(result.nodes) >= 1  # at least the file node

    def test_handles_malformed_source(self):
        parser = TypeScriptParser()
        result = parser.parse_file(Path("bad.ts"), b"}{}{function <<<>>>")
        # Must not raise — returns partial result
        assert isinstance(result.nodes, list)


class TestJavaParser:
    def test_extracts_method(self, sample_java_source: bytes):
        parser = JavaParser()
        result = parser.parse_file(Path("Main.java"), sample_java_source)
        func_nodes = [n for n in result.nodes if n.type == NodeType.FUNCTION]
        assert any(n.name == "run" for n in func_nodes)
        assert any(n.name == "hello" for n in func_nodes)

    def test_extracts_class(self, sample_java_source: bytes):
        parser = JavaParser()
        result = parser.parse_file(Path("Main.java"), sample_java_source)
        class_nodes = [n for n in result.nodes if n.type == NodeType.CLASS]
        assert any(n.name == "Main" for n in class_nodes)

    def test_extracts_import(self, sample_java_source: bytes):
        parser = JavaParser()
        result = parser.parse_file(Path("Main.java"), sample_java_source)
        import_edges = [e for e in result.edges if e.type == EdgeType.IMPORTS]
        assert len(import_edges) >= 1
