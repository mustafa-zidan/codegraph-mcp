"""Java parser using tree-sitter."""

from __future__ import annotations

import logging
from pathlib import Path

import tree_sitter_java as ts_java
from tree_sitter import Language, Parser
from tree_sitter import Node as TSNode

from codegraph_mcp.enums import EdgeType, NodeType
from codegraph_mcp.models import Edge, Node
from codegraph_mcp.parser.base import BaseParser, ParseResult, utf8_node_text

logger = logging.getLogger("codegraph_mcp.parser.java")

_JAVA_LANGUAGE = Language(ts_java.language())


class JavaParser(BaseParser):
    """Extract nodes and edges from Java source files."""

    language = "java"

    def parse_file(self, path: Path, source: bytes) -> ParseResult:
        result = ParseResult()
        module_name = path.stem

        parser = Parser(_JAVA_LANGUAGE)

        try:
            tree = parser.parse(source)
        except Exception:
            logger.exception("Tree-sitter parse failed: %s", path)
            return result

        file_id = self._make_id("file", str(path))
        result.add_node(
            Node(
                id=file_id,
                type=NodeType.FILE,
                name=path.name,
                file=str(path),
                language=self.language,
            )
        )

        self._walk(tree.root_node, path, module_name, file_id, result)
        return result

    # ------------------------------------------------------------------
    def _walk(
        self,
        node: TSNode,
        path: Path,
        module_name: str,
        file_id: str,
        result: ParseResult,
    ) -> None:
        try:
            if node.type == "import_declaration":
                self._handle_import(node, file_id, result)
            elif node.type == "method_declaration":
                self._handle_method(node, path, module_name, file_id, result)
            elif node.type == "class_declaration":
                self._handle_class(node, path, module_name, file_id, result)
            elif node.type == "method_invocation":
                self._handle_call(node, file_id, result)
        except Exception:
            logger.debug("Skipping malformed node at %s:%s", path, node.start_point)

        for child in node.children:
            self._walk(child, path, module_name, file_id, result)

    # --- handlers ---

    def _handle_import(
        self,
        node: TSNode,
        file_id: str,
        result: ParseResult,
    ) -> None:
        # import_declaration has a scoped_identifier child
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                import_path = utf8_node_text(child)
                target_id = self._make_id("module", import_path)
                result.add_node(
                    Node(
                        id=target_id,
                        type=NodeType.MODULE,
                        name=import_path,
                    )
                )
                result.add_edge(
                    Edge(
                        source=file_id,
                        target=target_id,
                        type=EdgeType.IMPORTS,
                    )
                )
                break

    def _handle_method(
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
        method_name = utf8_node_text(name_node)
        method_id = self._make_id("function", module_name, method_name)
        result.add_node(
            Node(
                id=method_id,
                type=NodeType.FUNCTION,
                name=method_name,
                file=str(path),
                language=self.language,
            )
        )
        result.add_edge(
            Edge(
                source=file_id,
                target=method_id,
                type=EdgeType.DEFINES,
            )
        )

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
        class_name = utf8_node_text(name_node)
        class_id = self._make_id("class", module_name, class_name)
        result.add_node(
            Node(
                id=class_id,
                type=NodeType.CLASS,
                name=class_name,
                file=str(path),
                language=self.language,
            )
        )
        result.add_edge(
            Edge(
                source=file_id,
                target=class_id,
                type=EdgeType.DEFINES,
            )
        )

    def _handle_call(
        self,
        node: TSNode,
        file_id: str,
        result: ParseResult,
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        callee = utf8_node_text(name_node)
        callee_id = self._make_id("function", callee)
        result.add_edge(
            Edge(
                source=file_id,
                target=callee_id,
                type=EdgeType.CALLS,
            )
        )
