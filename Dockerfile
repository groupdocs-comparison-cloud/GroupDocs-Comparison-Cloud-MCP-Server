# docker build -t groupdocs/mcp-groupdocs-conversion-cloud .

FROM python:3.12-slim-bookworm

WORKDIR /app

RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
RUN chown -R appuser:appuser /app

USER appuser

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,socket; p=int(os.environ.get('MCP_PORT','8000')); s=socket.create_connection(('127.0.0.1',p),timeout=3); s.close()"

CMD ["python", "src/server.py"]
