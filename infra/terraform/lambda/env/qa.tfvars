# Settings for the Lambda qa environment. Committed, so never put secrets here.
# Build the zip with scripts/build_lambda_zip.py before terraform plan/apply.

environment = "qa"

agent_model      = "bedrock"
bedrock_model_id = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"

# CORS origins the agent API accepts (never "*").
allowed_origins = "https://example.com"

mcp_memory_mb         = 512
agent_memory_mb       = 1024
mcp_timeout_seconds   = 30
agent_timeout_seconds = 180
