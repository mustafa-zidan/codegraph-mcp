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
SQLite Storage (persistent, indexed)
   ↓
Query Engine (BFS, DFS, shortest path, impact analysis)
   ↓
MCP Server (FastMCP — stdio, sse, or streamable-http transport)
   ↓
AI Agent (Cursor, Windsurf, Claude Code, etc.)
```

## Installation

```bash
git clone https://github.com/MrHappy439/codegraph-mcp.git
cd codegraph-mcp
pip install -e .
```

## Usage

### Analyze a repository

```bash
codegraph-mcp analyze ./your-repo
# or
python -m codegraph_mcp analyze ./your-repo
```

### Start MCP server (local — stdio)

```bash
codegraph-mcp serve ./your-repo
```

### Start MCP server (remote — SSE)

```bash
codegraph-mcp serve ./your-repo --transport streamable-http --port 8080
```

### Optional graph viewer (HTTP transports only)

When you use **SSE** or **streamable-http** (not `stdio`), you can expose a quick interactive graph in the browser:

```bash
codegraph-mcp serve ./your-repo --transport streamable-http --port 8080 --graph-ui
```

- Open `http://localhost:8080/graph` for a [vis-network](https://visjs.github.io/vis-network/docs/network/) view.
- Raw JSON: `GET /api/graph` (optional query `limit`, default `500`; caps node count for responsiveness).

`--graph-ui` is ignored for `stdio` (there is no HTTP server). You can also set `GRAPH_UI=1` instead of the flag.

## MCP Configuration

Add to your MCP client config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "python",
      "args": ["-m", "codegraph_mcp", "serve", "/path/to/your/repo"]
    }
  }
}
```

For remote servers (streamable-http or sse):

```json
{
  "mcpServers": {
    "codegraph": {
      "url": "http://your-server:8080/mcp"
    }
  }
}
```

## MCP Tools

| Tool                   | Description                       |
| ---------------------- | --------------------------------- |
| `search_nodes`         | Find nodes by name or type        |
| `trace_dependencies`   | What does this node depend on?    |
| `trace_dependents`     | What depends on this node?        |
| `impact_analysis`      | What breaks if this node changes? |
| `trace_path`           | Shortest path between two nodes   |
| `architecture_summary` | High-level graph summary          |

### Example queries

```
search_nodes(query="login", node_type="function")
impact_analysis(node_id="function:auth.loginUser")
trace_path(source_id="file:src/auth.ts", target_id="database:users")
architecture_summary()
```

## Supported Languages

- TypeScript / TSX
- Java
- Kotlin (`.kt`, `.kts`)

## Deployment

### Docker

```bash
docker build -t codegraph-mcp .
docker run -p 8080:8080 -v /path/to/repo:/repo codegraph-mcp
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

| Variable        | Default | Description                                                                                          |
| --------------- | ------- | ---------------------------------------------------------------------------------------------------- |
| `REPO_PATH`     | `.`     | Path to the repository to analyze                                                                    |
| `PORT`          | `8080`  | Port for SSE transport                                                                               |
| `MCP_TRANSPORT` | `stdio` | Transport mode: `stdio`, `sse`, or `streamable-http`                                                 |
| `GRAPH_UI`      | unset   | Set to `1` / `true` to enable `/graph` and `/api/graph` (same as `--graph-ui`; HTTP transports only) |

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
