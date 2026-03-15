"""TypeScript / TSX parser using tree-sitter."""

from __future__ import annotations

import logging
from pathlib import Path

import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Parser, Node as TSNode

from ..enums import EdgeType, NodeType
from ..models import Edge, Node
from .base import BaseParser, ParseResult

logger = logging.getLogger("codegraph_mcp.parser.typescript")

_TS_LANGUAGE = Language(ts_ts.language_typescript())
_TSX_LANGUAGE = Language(ts_ts.language_tsx())


class TypeScriptParser(BaseParser):
    """Extract nodes and edges from TypeScript / TSX source files."""

    language = "typescript"

    def parse_file(self, path: Path, source: bytes) -> ParseResult:
        result = ParseResult()
        module_name = path.stem
        lang = _TSX_LANGUAGE if path.suffix == ".tsx" else _TS_LANGUAGE

        parser = Parser(lang)

        try:
            tree = parser.parse(source)
        except Exception:
            logger.exception("Tree-sitter parse failed: %s", path)
            return result

        # File node
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

    # ------------------------------------------------------------------
    # Private tree-walk helpers
    # ------------------------------------------------------------------

    def _walk(
        self,
        node: TSNode,
        path: Path,
        module_name: str,
        file_id: str,
        result: ParseResult,
    ) -> None:
        """Depth-first walk over the AST, extracting relevant constructs."""
        try:
            if node.type == "import_statement":
                self._handle_import(node, path, file_id, result)
            elif node.type in ("function_declaration", "arrow_function",
                               "method_definition"):
                self._handle_function(node, path, module_name, file_id, result)
            elif node.type == "class_declaration":
                self._handle_class(node, path, module_name, file_id, result)
            elif node.type == "call_expression":
                self._handle_call(node, path, module_name, file_id, result)
        except Exception:
            logger.debug("Skipping malformed node at %s:%s", path, node.start_point)

        for child in node.children:
            self._walk(child, path, module_name, file_id, result)

    # --- handlers ---

    def _handle_import(
        self, node: TSNode, path: Path, file_id: str, result: ParseResult,
    ) -> None:
        source_node = node.child_by_field_name("source")
        if source_node is None:
            return
        import_path = source_node.text.decode("utf-8").strip("'\"")
        target_id = self._make_id("module", import_path)
        result.add_node(Node(
            id=target_id, type=NodeType.MODULE, name=import_path,
        ))
        result.add_edge(Edge(
            source=file_id, target=target_id, type=EdgeType.IMPORTS,
        ))

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

    def _handle_call(
        self,
        node: TSNode,
        path: Path,
        module_name: str,
        file_id: str,
        result: ParseResult,
    ) -> None:
        fn_node = node.child_by_field_name("function")
        if fn_node is None:
            return
        callee = fn_node.text.decode("utf-8")
        callee_id = self._make_id("function", callee)
        # We create a CALLS edge from the file to the callee
        result.add_edge(Edge(
            source=file_id, target=callee_id, type=EdgeType.CALLS,
        ))
