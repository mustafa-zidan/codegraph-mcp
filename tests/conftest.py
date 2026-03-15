"""Shared test fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_ts_source() -> bytes:
    return b"""
import { helper } from "./helper";

export function greet(name: string): string {
    return helper(name);
}

export class Greeter {
    run() {
        greet("world");
    }
}
"""


@pytest.fixture
def sample_java_source() -> bytes:
    return b"""
import com.example.Utils;

public class Main {
    public void run() {
        Utils.doSomething();
    }

    public String hello() {
        return "world";
    }
}
"""


@pytest.fixture
def sample_repo_dir(sample_ts_source: bytes) -> Path:
    """Create a tiny temporary repo with one .ts file."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "src"
        src.mkdir()
        (src / "index.ts").write_bytes(sample_ts_source)
        yield root
