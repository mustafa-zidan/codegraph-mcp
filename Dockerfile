FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY sample_repo/ sample_repo/

RUN pip install --no-cache-dir .

ENV REPO_PATH=/app
ENV PORT=8080
ENV MCP_TRANSPORT=streamable-http

EXPOSE 8080

CMD ["python", "-m", "codegraph_mcp", "serve", "/app", "--transport", "streamable-http"]
