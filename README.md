# CodeGraph MCP

**An MCP server that builds a machine-readable knowledge graph of your codebase.**

CodeGraph MCP scans a repository, parses source files with [Tree-sitter](https://tree-sitter.github.io/), and exposes
structured architectural queries via the [Model Context Protocol](https://modelcontextprotocol.io/) — enabling AI coding
agents to reason about dependencies, impact analysis, and system architecture.

## Architecture

```
Repository
   ↓
File Scanner (lazy, generator-based)
   ↓
Parser Layer (Tree-sitter: TypeScript, Java, Kotlin)
   ↓
Graph Builder (NetworkX DiGraph)
   ↓
Kuzu Storage (embedded graph DB + full-text search)
   ↓
Query Engine (BFS, shortest path, impact analysis)
   ↓
MCP Server (FastMCP — stdio, sse, or streamable-http transport)
   ↓
AI Agent (Cursor, Windsurf, Claude Code, etc.)
```

Graph traversals run in **NetworkX**. The **Kuzu** database persists nodes and edges and powers **BM25-style** lexical
`search_nodes` (with substring fallback). Optional **semantic** search (`uvx --with "codegraph-mcp[semantic]" …`, or
`uv sync --extra semantic` in a clone) stores embedding vectors in NumPy files next to the Kuzu path.

## Documentation

- **[Setup and MCP](docs/setup-and-mcp.md)** — install, first-time analyze, environment variables, stdio vs HTTP,
  **Claude Desktop**, **Cursor**, **VS Code**, remote URL, Docker, troubleshooting.
- **[Local build and semantic](docs/local-build-and-semantic.md)** — develop from a clone, `analyze --semantic-index`,
  embedding backends, and serving with the vector index.
- **[Release cycle](docs/release-cycle.md)** — versioning and PyPI releases for maintainers.

## Installation

**`uvx codegraph-mcp` only works after the package is published on PyPI.** Until then, use **`uv run`** from a git clone
(see below).

### With PyPI (uvx)

[`uvx`](https://docs.astral.sh/uv/guides/tools/) runs the app from PyPI. Core install:

```bash
uvx codegraph-mcp --help
```

With the optional **`[semantic]`** extra (NumPy + `search_nodes_semantic` / vector index), use `--with` so the same tool
env includes NumPy:

```bash
uvx --with "codegraph-mcp[semantic]" codegraph-mcp --help
```

### From a git clone (development)

```bash
git clone https://github.com/MrHappy439/codegraph-mcp.git
cd codegraph-mcp
uv sync --extra dev --extra semantic
uv run codegraph-mcp --help
```

Omit `--extra semantic` if you do not need semantic search or `analyze --semantic-index` (core graph + FTS still work).

## Usage

Examples below use **`uvx`** (PyPI). For a **local clone**, replace `uvx …` with `uv run …` (after `uv sync --extra dev`
and optional `--extra semantic`) or prefix with `uvx --from /path/to/codegraph-mcp` when supported.

### Analyze a repository

```bash
uvx codegraph-mcp analyze ./your-repo
```

Build the vector index (needs **`[semantic]`** in the environment — see Installation):

```bash
uvx --with "codegraph-mcp[semantic]" codegraph-mcp analyze ./your-repo --semantic-index
```

### Start MCP server (local — stdio)

```bash
uvx codegraph-mcp serve ./your-repo
```

With semantic tooling available to the server process:

```bash
uvx --with "codegraph-mcp[semantic]" codegraph-mcp serve ./your-repo
```

### Start MCP server (remote — SSE)

```bash
uvx codegraph-mcp serve ./your-repo --transport streamable-http --port 3847
```

### Optional graph viewer (HTTP transports only)

When you use **SSE** or **streamable-http** (not `stdio`), you can expose a quick interactive graph in the browser:

```bash
uvx codegraph-mcp serve ./your-repo --transport streamable-http --port 3847 --graph-ui
```

- Open `http://localhost:3847/graph` for a [vis-network](https://visjs.github.io/vis-network/docs/network/) view.
- Raw JSON: `GET /api/graph` (optional query `limit`, default `500`; caps node count for responsiveness).

`--graph-ui` is ignored for `stdio` (there is no HTTP server). You can also set `GRAPH_UI=1` instead of the flag.

## MCP configuration

**Full guide:** [docs/setup-and-mcp.md](docs/setup-and-mcp.md) — install steps, first-time analyze, `uvx` / `uv run`,
Docker, and examples for **Claude Desktop**, **Cursor**, **VS Code**, and remote URLs.

### Quick reference (stdio, recommended)

Requires [`uv`](https://docs.astral.sh/uv/) on `PATH` so `uvx` is available (and **PyPI** must list `codegraph-mcp`, or
use `uv run` from a clone — see [docs/setup-and-mcp.md](docs/setup-and-mcp.md)).

**Core** (lexical `search_nodes` only):

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "uvx",
      "args": ["codegraph-mcp", "serve", "/absolute/path/to/your/repo"]
    }
  }
}
```

**With `[semantic]`** (NumPy + `search_nodes_semantic` after you build an index):

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "uvx",
      "args": [
        "--with",
        "codegraph-mcp[semantic]",
        "codegraph-mcp",
        "serve",
        "/absolute/path/to/your/repo"
      ]
    }
  }
}
```

**From a git clone** (no PyPI), with semantic:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/codegraph-mcp",
        "codegraph-mcp",
        "serve",
        "/absolute/path/to/your/repo"
      ]
    }
  }
}
```

Use `uv sync --extra dev --extra semantic` in that clone before starting the MCP client.

Optional env (e.g. custom Kuzu path):

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "uvx",
      "args": ["codegraph-mcp", "serve", "/path/to/repo"],
      "env": {
        "CODEGRAPH_STORE": "/path/to/repo/.codegraph/codegraph.kuzu"
      }
    }
  }
}
```

### Remote server (streamable-http / SSE)

```json
{
  "mcpServers": {
    "codegraph": {
      "url": "http://your-server:3847/mcp"
    }
  }
}
```

Start the process with `uvx codegraph-mcp serve /repo --transport streamable-http --port 3847` (see the doc for Docker).

## MCP Tools

| Tool                    | Description                                       |
| ----------------------- | ------------------------------------------------- |
| `search_nodes`          | Lexical search (FTS + substring fallback) by type |
| `search_nodes_semantic` | Cosine similarity (requires `[semantic]` + index) |
| `trace_dependencies`    | What does this node depend on?                    |
| `trace_dependents`      | What depends on this node?                        |
| `impact_analysis`       | What breaks if this node changes?                 |
| `trace_path`            | Shortest path between two nodes                   |
| `architecture_summary`  | High-level graph summary                          |

### Example queries

```
search_nodes(query="login", node_type="function")
impact_analysis(node_id="function:auth.loginUser")
trace_path(source_id="file:src/auth.ts", target_id="database:users")
architecture_summary()
```

## Semantic search (optional)

1. Install the extra into the tool env, e.g.
   `uvx --with "codegraph-mcp[semantic]" codegraph-mcp analyze ./repo --semantic-index` (or `uv sync --extra semantic`
   when developing from a clone).
2. **Embedding backend** (env `CODEGRAPH_EMBED_BACKEND`):
   - `openai` (default): `POST {OPENAI_BASE_URL}/v1/embeddings` — works with LM Studio, Ollama (OpenAI mode), OpenAI,
     etc.
   - `local`: in-process models via `sentence-transformers` — install separately: `pip install sentence-transformers`.
3. Build the index when analyzing: `CODEGRAPH_BUILD_SEMANTIC_INDEX=1` or
   `codegraph-mcp analyze ./repo --semantic-index`. This writes `codegraph.vectors.npz` and `codegraph.embeddings.json`
   next to the Kuzu file (`--store` / `CODEGRAPH_STORE`).

| Variable                      | Purpose                                                                                                                                                                                                          |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CODEGRAPH_EMBED_BACKEND`     | `openai` or `local`                                                                                                                                                                                              |
| `CODEGRAPH_EMBED_BATCH_SIZE`  | OpenAI HTTP backend: inputs per request (default `64`). If the server returns fewer vectors than inputs, the client retries one string per request automatically; set `1` to skip the slow failed batch attempt. |
| `OPENAI_BASE_URL`             | e.g. `http://127.0.0.1:1234/v1` for LM Studio                                                                                                                                                                    |
| `OPENAI_API_KEY`              | Bearer token (dummy if the server ignores it)                                                                                                                                                                    |
| `OPENAI_EMBEDDING_MODEL`      | Model id for `/v1/embeddings`                                                                                                                                                                                    |
| `CODEGRAPH_LOCAL_EMBED_MODEL` | Sentence-transformers model id when backend is `local`                                                                                                                                                           |

## Supported Languages

- TypeScript / TSX
- Java
- Kotlin (`.kt`, `.kts`)

## Deployment

### Docker

```bash
docker build -t codegraph-mcp .
docker run -p 3847:3847 -v /path/to/repo:/repo codegraph-mcp
```

### Railway

1. Connect the GitHub repo at [railway.app](https://railway.app)
2. Set environment variable: `REPO_PATH=/repo`
3. Deploy — Railway uses `railway.json` automatically

### Fly.io

```bash
fly launch
fly deploy
```

## Environment Variables

| Variable                         | Default          | Description                                                                                          |
| -------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------- |
| `REPO_PATH`                      | `.`              | Path to the repository to analyze                                                                    |
| `CODEGRAPH_STORE`                | `codegraph.kuzu` | Kuzu database path (overrides default `codegraph.kuzu` when CLI does not pass `--store`)             |
| `PORT`                           | `3847`           | Port for SSE transport                                                                               |
| `MCP_TRANSPORT`                  | `stdio`          | Transport mode: `stdio`, `sse`, or `streamable-http`                                                 |
| `GRAPH_UI`                       | unset            | Set to `1` / `true` to enable `/graph` and `/api/graph` (same as `--graph-ui`; HTTP transports only) |
| `CODEGRAPH_BUILD_SEMANTIC_INDEX` | unset            | Set to `1` / `true` when serving to build the vector index on full analyze (optional)                |

## Development

Install with dev extras (e.g. [uv](https://docs.astral.sh/uv/) or pip):

```bash
uv sync --extra dev
# or: pip install -e ".[dev]"
```

Lint and format:

```bash
ruff check src tests
ruff format src tests
```

Markdown (see [`.mdformat.toml`](.mdformat.toml); [GFM](https://github.github.com/gfm/) tables and wrapping):

```bash
mdformat README.md CHANGELOG.md docs/
mdformat --check README.md CHANGELOG.md docs/
```

Static typing:

```bash
mypy src
```

Tests:

```bash
pytest tests/ -v
```

Optional [pre-commit](https://pre-commit.com/) hooks (Ruff lint + format on commit):

```bash
pip install pre-commit
pre-commit install
```

## CI and PyPI releases

[`.github/workflows/test.yml`](.github/workflows/test.yml) runs on push/PR to `main`, `master`, or `develop`:
`uv sync --extra dev`, Ruff, mdformat, Mypy, and pytest (matrix: Ubuntu / macOS / Windows × Python 3.10 / 3.12 / 3.13).

To publish **[codegraph-mcp on PyPI](https://pypi.org/p/codegraph-mcp)**:

1. Bump `version` in [`pyproject.toml`](pyproject.toml) and update [`CHANGELOG.md`](CHANGELOG.md) for that version,
   merge to your default branch.
2. In PyPI → your project → **Settings** → **Publishing**, add a **trusted publisher** for this GitHub repo (workflow:
   `release.yml`, environment: `pypi`).
3. In GitHub → **Settings** → **Environments**, create an environment named `pypi` (optionally add protection rules).
4. Run **Actions** → **Release** → **Run workflow**, enter the same version string as in `pyproject.toml`.

The workflow creates an annotated tag `vX.Y.Z`, runs `uv build`, publishes with
[OIDC](https://docs.pypi.org/trusted-publishers/), signs artifacts with Sigstore, and creates a GitHub Release. Inspired
by the [eurydice](https://github.com/mustafa-zidan/eurydice) test/release workflows.

Full maintainer guide: [docs/release-cycle.md](docs/release-cycle.md).

## License

MIT — see [LICENSE](LICENSE).
