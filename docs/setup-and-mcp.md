# Setup and MCP configuration

This guide walks through running CodeGraph MCP with **[uv](https://docs.astral.sh/uv/)** (recommended), analyzing a
repository, and wiring it into common MCP clients.

## Prerequisites

- **[uv](https://docs.astral.sh/uv/install/)** on your `PATH` (provides `uvx` to run PyPI tools without a global pip
  install).
- **Python 3.10+** (3.12+ recommended; Kuzu ships wheels for 3.10–3.13 on common platforms). uv picks a compatible
  interpreter for the tool environment.
- A **repository** containing supported languages (TypeScript/TSX, Java, Kotlin).

## Run without installing (uvx)

[`uvx`](https://docs.astral.sh/uv/guides/tools/) runs the published package from PyPI in an isolated environment. If you
see “package not found”, the project is not on PyPI yet — use **From a git clone** below.

**Core:**

```bash
uvx codegraph-mcp --help
uvx codegraph-mcp analyze /path/to/your-app
uvx codegraph-mcp serve /path/to/your-app
```

**With `[semantic]`** (NumPy, `search_nodes_semantic`, `--semantic-index`): pass `--with` so the tool environment
includes the extra:

```bash
uvx --with "codegraph-mcp[semantic]" codegraph-mcp --help
uvx --with "codegraph-mcp[semantic]" codegraph-mcp analyze /path/to/your-app --semantic-index
uvx --with "codegraph-mcp[semantic]" codegraph-mcp serve /path/to/your-app
```

## Install into a persistent tool environment (optional)

```bash
uv tool install codegraph-mcp
codegraph-mcp --help
```

With semantic:

```bash
uv tool install "codegraph-mcp[semantic]"
```

## From a git clone (development)

Use this until **`codegraph-mcp` is on PyPI**. Include **`--extra semantic`** when you need vector search /
`--semantic-index`.

```bash
git clone https://github.com/MrHappy439/codegraph-mcp.git
cd codegraph-mcp
uv sync --extra dev --extra semantic
uv run codegraph-mcp analyze /path/to/repo
uv run codegraph-mcp analyze /path/to/repo --semantic-index
uv run codegraph-mcp serve /path/to/target-repo
```

Core only (no semantic):

```bash
uv sync --extra dev
uv run codegraph-mcp serve /path/to/target-repo
```

## First-time repository analysis

Point at the **root of the project** you want to graph (the folder that contains `src/`, `package.json`, etc.).

```bash
cd /path/to/your-app
uvx codegraph-mcp analyze .
```

This writes a Kuzu database **`codegraph.kuzu`** in the current working directory by default. To put the store
elsewhere:

```bash
uvx codegraph-mcp analyze . --store /path/to/cache/my-project.kuzu
```

Equivalent environment variable (useful in Docker or CI):

```bash
export CODEGRAPH_STORE=/data/codegraph.kuzu
uvx codegraph-mcp analyze /repo
```

Optional **semantic** vector index (requires `[semantic]` and embedding configuration):

```bash
export CODEGRAPH_BUILD_SEMANTIC_INDEX=1
export OPENAI_BASE_URL=http://127.0.0.1:1234/v1   # example: LM Studio
export OPENAI_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
uvx --with "codegraph-mcp[semantic]" codegraph-mcp analyze . --semantic-index
```

That produces `codegraph.vectors.npz` and `codegraph.embeddings.json` next to the Kuzu path (see the main README).

## Run the MCP server (stdio — local)

Most desktop agents use **stdio**: they spawn your process and talk over stdin/stdout.

```bash
uvx codegraph-mcp serve /absolute/path/to/your-app
```

### Custom store path

```bash
uvx codegraph-mcp serve /path/to/repo --store /path/to/repo/.codegraph/codegraph.kuzu
```

Or set `CODEGRAPH_STORE` so you do not repeat it in every config:

```bash
export CODEGRAPH_STORE=/path/to/repo/.codegraph/codegraph.kuzu
uvx codegraph-mcp serve /path/to/repo
```

## Remote transport (HTTP)

For clients that connect to a **URL** instead of spawning a process, start the server with SSE or streamable HTTP:

```bash
export REPO_PATH=/repo
export MCP_TRANSPORT=streamable-http
export PORT=3847
uvx codegraph-mcp serve /repo --transport streamable-http --port 3847
```

The MCP endpoint path depends on the FastMCP version; clients often expect something like `http://localhost:3847/mcp` —
check your client’s docs and the server logs on startup.

Optional graph UI (same host):

```bash
uvx codegraph-mcp serve /repo --transport streamable-http --port 3847 --graph-ui
# open http://localhost:3847/graph
```

## MCP client examples

Configs differ by product. Use **absolute paths** for repos. Prefer **`uvx`** so you do not depend on a global Python or
`pip install`.

### Claude Desktop (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (path may vary on Windows/Linux).

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "uvx",
      "args": ["codegraph-mcp", "serve", "/Users/you/projects/my-app"]
    }
  }
}
```

With semantic extra in the same env:

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
        "/Users/you/projects/my-app"
      ]
    }
  }
}
```

If you used `uv tool install codegraph-mcp` and the shim is on `PATH`:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "codegraph-mcp",
      "args": ["serve", "/Users/you/projects/my-app"]
    }
  }
}
```

Restart Claude Desktop after saving.

### Cursor

Cursor reads MCP settings from the editor MCP configuration (UI: **Settings → MCP** or project `.cursor/mcp.json`
depending on version).

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "uvx",
      "args": ["codegraph-mcp", "serve", "/Users/you/projects/my-app"],
      "env": {
        "CODEGRAPH_STORE": "/Users/you/projects/my-app/.codegraph/codegraph.kuzu"
      }
    }
  }
}
```

Match the structure your Cursor build expects.

### VS Code (GitHub Copilot MCP / MCP extension)

Many VS Code MCP extensions expect a similar `command` + `args` block. Example:

```json
{
  "servers": {
    "codegraph": {
      "type": "stdio",
      "command": "uvx",
      "args": ["codegraph-mcp", "serve", "/Users/you/projects/my-app"]
    }
  }
}
```

Refer to the extension’s schema — keys may be `mcpServers` or `servers`.

### Remote URL client

When the server runs with streamable HTTP/SSE:

```json
{
  "mcpServers": {
    "codegraph": {
      "url": "http://localhost:3847/mcp"
    }
  }
}
```

Replace host/port with your deployment. Use HTTPS and authentication in production.

## Tools you get

After the server starts, the client can call tools such as:

| Tool                    | Typical use                                    |
| ----------------------- | ---------------------------------------------- |
| `search_nodes`          | Find symbols by name / FTS                     |
| `search_nodes_semantic` | Similarity search (needs index + `[semantic]`) |
| `trace_dependencies`    | Downstream deps from a node id                 |
| `trace_dependents`      | Who depends on this node                       |
| `impact_analysis`       | Blast radius of a change                       |
| `trace_path`            | Shortest path between two nodes                |
| `architecture_summary`  | Counts and language summary                    |

### Example prompts for the agent

- “Use `architecture_summary` and summarize this codebase.”
- “Call `search_nodes` with `query` login and `node_type` function, then `trace_dependents` on the first hit.”
- “Run `impact_analysis` on `function:auth.login` with `max_depth` 5.”

Node ids are strings like `function:file.funcName` or `file:path/to/file.ts` — use `search_nodes` first if you are
unsure.

## Docker

The image runs streamable HTTP by default (see `Dockerfile`). Mount the repo and set paths:

```bash
docker run --rm -p 3847:3847 \
  -e REPO_PATH=/repo \
  -v /path/to/your-app:/repo \
  codegraph-mcp
```

Persist the Kuzu store on a volume if you want reuse between container restarts:

```bash
-v codegraph-data:/data \
-e CODEGRAPH_STORE=/data/codegraph.kuzu \
-v /path/to/your-app:/repo
```

## Troubleshooting

| Issue                    | What to check                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------ |
| `uvx` not found          | Install [uv](https://docs.astral.sh/uv/install/) and ensure it is on `PATH`.         |
| Server exits immediately | Repo path wrong or not readable; run `uvx codegraph-mcp analyze` on that path first. |
| “Graph not initialized”  | Client started the wrong command or wrong working directory.                         |
| Empty `search_nodes`     | Run analyze; confirm `codegraph.kuzu` exists and is non-empty.                       |
| Semantic tool errors     | Use `uvx --with "codegraph-mcp[semantic]" …`, build index; set embedding URL/model.  |
| Kuzu install fails       | Use a Python version with prebuilt wheels (e.g. 3.12) or install build tools.        |

For release and packaging details, see [Release cycle](release-cycle.md).
