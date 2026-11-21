# syntax=docker/dockerfile:1
#
# One image for the three Lambda functions (flights MCP, calendar MCP, agent API).
# Build from the repository root so the agent and servers packages are in context:
#   docker build -f lambda/Dockerfile -t mcp-demo-lambda .
# Terraform (infra/lambda) sets each function's command to pick its ASGI app.

FROM python:3.14-slim

# Lambda Web Adapter: the app listens on AWS_LWA_PORT and the adapter proxies invocations to it.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/health

# The adapter runs as a Lambda extension; no application code change is needed for it.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent ./agent
COPY servers ./servers
COPY lambda/lambda_handlers.py ./lambda_handlers.py

CMD ["uvicorn", "lambda_handlers:flights_app", "--host", "0.0.0.0", "--port", "8080"]
