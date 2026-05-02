FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git curl unzip xz-utils ca-certificates && rm -rf /var/lib/apt/lists/*

COPY workers/daemon/requirements.txt /app/workers/daemon/requirements.txt
RUN pip install --no-cache-dir -r /app/workers/daemon/requirements.txt

COPY workers /app/workers
COPY templates /app/templates
COPY prompts /app/prompts

ENV PYTHONPATH=/app/workers/daemon
CMD ["python", "-m", "daemon.main"]
