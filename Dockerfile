# syntax=docker/dockerfile:1

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent ./agent
COPY servers ./servers

# Bind MCP servers to all interfaces inside the container. The agent overrides
# AGENT_API_HOST separately.
ENV MCP_HOST=0.0.0.0

# The command is supplied per service (flight, calendar, or agent) at deploy time.
CMD ["python", "-m", "agent.api"]
