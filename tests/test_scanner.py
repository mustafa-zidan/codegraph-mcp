"""Tests for utils/scanner.py."""

import tempfile
from pathlib import Path

from codegraph_mcp.utils.scanner import detect_language, scan_repository


def test_scan_finds_ts_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "index.ts").write_text("console.log('hi');")
        (root / "readme.md").write_text("# hi")
        (root / "Main.java").write_text("class Main {}")

        files = list(scan_repository(root))
        names = {f.name for f in files}
        assert "index.ts" in names
        assert "Main.java" in names
        assert "readme.md" not in names


def test_scan_skips_node_modules():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        nm = root / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.ts").write_text("export default 1;")
        (root / "app.ts").write_text("import x from 'pkg';")

        files = list(scan_repository(root))
        assert len(files) == 1
        assert files[0].name == "app.ts"


def test_detect_language():
    assert detect_language(Path("foo.ts")) == "typescript"
    assert detect_language(Path("foo.tsx")) == "typescript"
    assert detect_language(Path("Main.java")) == "java"
    assert detect_language(Path("foo.kt")) == "kotlin"
    assert detect_language(Path("build.gradle.kts")) == "kotlin"
    assert detect_language(Path("readme.md")) is None
