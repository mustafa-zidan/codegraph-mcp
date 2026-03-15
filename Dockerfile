FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir .

ENV REPO_PATH=/repo
ENV PORT=8080
ENV MCP_TRANSPORT=sse

EXPOSE 8080

CMD ["python", "-m", "codegraph_mcp", "serve", "--transport", "sse"]
