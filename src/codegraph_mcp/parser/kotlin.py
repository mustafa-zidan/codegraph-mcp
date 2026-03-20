"""Kotlin parser using tree-sitter."""

from __future__ import annotations

import logging
from pathlib import Path

import tree_sitter_kotlin as ts_kotlin
from tree_sitter import Language, Parser, Node as TSNode

from ..enums import EdgeType, NodeType
from ..models import Edge, Node
from .base import BaseParser, ParseResult

logger = logging.getLogger("codegraph_mcp.parser.kotlin")

_KOTLIN_LANGUAGE = Language(ts_kotlin.language())


class KotlinParser(BaseParser):
    """Extract nodes and edges from Kotlin source files (.kt / .kts)."""

    language = "kotlin"

    def parse_file(self, path: Path, source: bytes) -> ParseResult:
        result = ParseResult()
        module_name = path.stem

        parser = Parser(_KOTLIN_LANGUAGE)

        try:
            tree = parser.parse(source)
        except Exception:
            logger.exception("Tree-sitter parse failed: %s", path)
            return result

        file_id = self._make_id("file", str(path))
        result.add_node(Node(
            id=file_id,
            type=NodeType.FILE,
            name=path.name,
            file=str(path),
            language=self.language,
        ))

        self._walk(tree.root_node, path, module_name, file_id, result)
        return result

    def _walk(
        self,
        node: TSNode,
        path: Path,
        module_name: str,
        file_id: str,
        result: ParseResult,
    ) -> None:
        try:
            if node.type == "import":
                self._handle_import(node, file_id, result)
            elif node.type == "function_declaration":
                self._handle_function(node, path, module_name, file_id, result)
            elif node.type == "class_declaration":
                self._handle_class(node, path, module_name, file_id, result)
            elif node.type == "object_declaration":
                self._handle_object(node, path, module_name, file_id, result)
            elif node.type == "call_expression":
                self._handle_call(node, file_id, result)
        except Exception:
            logger.debug("Skipping malformed node at %s:%s", path, node.start_point)

        for child in node.children:
            self._walk(child, path, module_name, file_id, result)

    def _handle_import(
        self, node: TSNode, file_id: str, result: ParseResult,
    ) -> None:
        for child in node.children:
            if child.type == "qualified_identifier":
                import_path = child.text.decode("utf-8")
                target_id = self._make_id("module", import_path)
                result.add_node(Node(
                    id=target_id, type=NodeType.MODULE, name=import_path,
                ))
                result.add_edge(Edge(
                    source=file_id, target=target_id, type=EdgeType.IMPORTS,
                ))
                break

    def _handle_function(
        self,
        node: TSNode,
        path: Path,
        module_name: str,
        file_id: str,
        result: ParseResult,
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        func_name = name_node.text.decode("utf-8")
        func_id = self._make_id("function", module_name, func_name)
        result.add_node(Node(
            id=func_id,
            type=NodeType.FUNCTION,
            name=func_name,
            file=str(path),
            language=self.language,
        ))
        result.add_edge(Edge(
            source=file_id, target=func_id, type=EdgeType.DEFINES,
        ))

    def _handle_class(
        self,
        node: TSNode,
        path: Path,
        module_name: str,
        file_id: str,
        result: ParseResult,
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode("utf-8")
        class_id = self._make_id("class", module_name, class_name)
        result.add_node(Node(
            id=class_id,
            type=NodeType.CLASS,
            name=class_name,
            file=str(path),
            language=self.language,
        ))
        result.add_edge(Edge(
            source=file_id, target=class_id, type=EdgeType.DEFINES,
        ))

    def _handle_object(
        self,
        node: TSNode,
        path: Path,
        module_name: str,
        file_id: str,
        result: ParseResult,
    ) -> None:
        """Treat `object Foo` like a class for graph purposes."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        obj_name = name_node.text.decode("utf-8")
        class_id = self._make_id("class", module_name, obj_name)
        result.add_node(Node(
            id=class_id,
            type=NodeType.CLASS,
            name=obj_name,
            file=str(path),
            language=self.language,
        ))
        result.add_edge(Edge(
            source=file_id, target=class_id, type=EdgeType.DEFINES,
        ))

    def _handle_call(
        self, node: TSNode, file_id: str, result: ParseResult,
    ) -> None:
        if not node.children:
            return
        callee_expr = node.children[0]
        callee = self._callee_name(callee_expr)
        if callee is None:
            return
        callee_id = self._make_id("function", callee)
        result.add_edge(Edge(
            source=file_id, target=callee_id, type=EdgeType.CALLS,
        ))

    @staticmethod
    def _callee_name(node: TSNode) -> str | None:
        """Best-effort callee identifier (mirrors Java/TS name-only resolution)."""
        if node.type == "identifier":
            return node.text.decode("utf-8")
        if node.type == "navigation_expression":
            for child in reversed(node.children):
                if child.type == "identifier":
                    return child.text.decode("utf-8")
        if node.type == "call_expression":
            return KotlinParser._callee_name(node.children[0]) if node.children else None
        return node.text.decode("utf-8")[:200] or None
