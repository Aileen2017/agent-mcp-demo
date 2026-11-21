#!/bin/sh
# Start script for the zip package. The Lambda Web Adapter layer runs this as the handler
# (AWS_LAMBDA_EXEC_WRAPPER=/opt/bootstrap) and proxies Function URL requests to the app
# on AWS_LWA_PORT.
#
# ASGI_APP picks the app for each function (see lambda/lambda_handlers.py).
set -eu

cd "${LAMBDA_TASK_ROOT:-/var/task}"
exec python3 -m uvicorn "${ASGI_APP:-lambda_handlers:agent_app}" \
    --host 0.0.0.0 --port "${AWS_LWA_PORT:-8080}"
