# Settings for the Lambda dev environment. Committed, so never put secrets here.
# Build the zip with scripts/build_lambda_zip.py before terraform plan/apply.

environment = "dev"

agent_model      = "bedrock"
bedrock_model_id = "global.amazon.nova-2-lite-v1:0"

# CORS origins the agent API accepts (never "*").
allowed_origins = "https://example.com"

mcp_memory_mb         = 512
agent_memory_mb       = 1024
mcp_timeout_seconds   = 30
agent_timeout_seconds = 180
