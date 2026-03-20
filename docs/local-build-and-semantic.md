# Local build, semantic index, and embeddings

This guide is for working **from a git clone**: install the project locally, build a Kuzu graph **with**
`--semantic-index`, then run **`serve`** so tools like `search_nodes_semantic` work. For PyPI installs and MCP client
JSON snippets, see [Setup and MCP](setup-and-mcp.md).

## Prerequisites

- **Python 3.10+** (3.12 is a good default; Kuzu publishes wheels for common platforms).
- **[uv](https://docs.astral.sh/uv/install/)** (recommended) or another PEP 517 installer.
- Supported languages in the target repo: TypeScript/TSX, Java, Kotlin.

## 1. Build and install the library locally

Clone and sync dependencies. The **`semantic`** extra pulls in **NumPy**, which is required for the vector files
(`*.vectors.npz`).

```bash
git clone https://github.com/MrHappy439/codegraph-mcp.git
cd codegraph-mcp
uv sync --extra dev --extra semantic
```

Smoke-test the CLI:

```bash
uv run codegraph-mcp --help
```

Equivalent without uv (from repo root, after creating a venv):

```bash
pip install -e ".[semantic,dev]"
codegraph-mcp --help
```

**Core-only** (no semantic index / `search_nodes_semantic`): omit `--extra semantic` and skip `--semantic-index` below.

## 2. Configure embeddings before analysis

The semantic index stores one vector per graph node. Another embedding call runs **at query time** when you use
`search_nodes_semantic`, so the **same backend and model** should be used for both index build and serving — otherwise
dimensions or semantics will not line up.

### Backend: OpenAI-compatible HTTP (default)

`CODEGRAPH_EMBED_BACKEND` defaults to **`openai`**. The client calls:

`POST {OPENAI_BASE_URL}/v1/embeddings`

| Variable                     | Role                                                                                                                                                                        |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CODEGRAPH_EMBED_BATCH_SIZE` | Strings per `/v1/embeddings` request (default `64`). If the server returns fewer vectors than inputs, the client retries one-by-one; set `1` to avoid a failed batch first. |
| `OPENAI_BASE_URL`            | API root including `/v1` suffix as used by your server (e.g. `https://api.openai.com/v1` or `http://127.0.0.1:1234/v1` for LM Studio).                                      |
| `OPENAI_API_KEY`             | Bearer token; use a placeholder if the local server ignores auth.                                                                                                           |
| `OPENAI_EMBEDDING_MODEL`     | Model id your server exposes for embeddings.                                                                                                                                |

Example (local LM Studio):

```bash
export OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export OPENAI_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
# optional if the server does not require a key:
export OPENAI_API_KEY=local
```

### Backend: local `sentence-transformers`

Set:

```bash
export CODEGRAPH_EMBED_BACKEND=local
# optional; default is all-MiniLM-L6-v2
export CODEGRAPH_LOCAL_EMBED_MODEL=all-MiniLM-L6-v2
```

Install the library **in the same environment** as CodeGraph:

```bash
uv pip install sentence-transformers
# or: pip install sentence-transformers
```

Note: `sentence-transformers` is **not** part of the `semantic` extra today; only NumPy is.

## 3. Analyze a repository with `--semantic-index`

From your clone, with embedding env vars set (if not using public OpenAI defaults):

```bash
cd /path/to/target-repo
uv run --directory /path/to/codegraph-mcp codegraph-mcp analyze . --semantic-index
```

Or, if your shell is already in the `codegraph-mcp` repo:

```bash
uv run codegraph-mcp analyze /path/to/target-repo --semantic-index
```

What this does:

1. Scans the repo and builds the graph.
2. Writes the Kuzu database (default **`./codegraph.kuzu`** in the **current working directory** unless you pass
   `--store`).
3. Sets `CODEGRAPH_BUILD_SEMANTIC_INDEX` internally when you pass `--semantic-index`, then writes:
   - **`{store}.vectors.npz`** — compressed matrix of node embeddings
   - **`{store}.embeddings.json`** — small metadata sidecar

Use an explicit store when you want everything in one place:

```bash
uv run codegraph-mcp analyze /path/to/repo \
  --store /path/to/repo/.codegraph/codegraph.kuzu \
  --semantic-index
```

That produces `/path/to/repo/.codegraph/codegraph.vectors.npz` (same basename stem as the `.kuzu` path).

You can instead set `CODEGRAPH_BUILD_SEMANTIC_INDEX=1` and run `analyze` **without** the flag; the CLI flag is shorthand
for that.

## 4. Serve the same repo and store

Point **`serve`** at the **same repository root** and **same `--store`** (or `CODEGRAPH_STORE`) so the server finds the
Kuzu DB and the sibling `*.vectors.npz`.

Keep the **same embedding environment variables** as during `analyze` (especially model and backend).

```bash
export CODEGRAPH_STORE=/path/to/repo/.codegraph/codegraph.kuzu
#(re-apply OPENAI_* or CODEGRAPH_EMBED_BACKEND / CODEGRAPH_LOCAL_EMBED_MODEL as above)

uv run codegraph-mcp serve /path/to/repo
```

For HTTP transport (e.g. remote MCP):

```bash
uv run codegraph-mcp serve /path/to/repo \
  --transport streamable-http \
  --port 3847
```

### When does the server rebuild the semantic index?

On startup, **`initialize` loads from Kuzu** if it already has nodes; it does **not** rescan the repo and does **not**
rebuild the vector index in that case.

The vector index is built after a **full repository scan** inside `serve` only when the store is missing or empty —
**and** only if `CODEGRAPH_BUILD_SEMANTIC_INDEX` is truthy in the environment. The `serve` subcommand does **not**
accept `--semantic-index`; use **`analyze ... --semantic-index`** (or set the env var) before relying on
`search_nodes_semantic`.

**Practical workflow:** run **`analyze ... --semantic-index`** whenever the codebase changes and you want an up-to-date
semantic index; then **`serve`** with matching `CODEGRAPH_STORE` and embedding settings.

## 5. Verify semantic search

With the MCP client connected, call **`search_nodes_semantic`** with a natural-language phrase. If something is wrong,
typical causes are:

- `[semantic]` / NumPy not installed in the **same** env as `serve`.
- Missing `*.vectors.npz` next to the Kuzu file (re-run analyze with `--semantic-index`).
- Query-time embedding config differs from build-time (different model or backend).

## Related docs

- [Setup and MCP](setup-and-mcp.md) — `uvx`, client configs, Docker.
- [README](../README.md) — architecture overview and full env var tables.
