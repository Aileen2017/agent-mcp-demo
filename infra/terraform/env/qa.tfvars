# Settings for the qa environment. Passed by the Infra workflows with -var-file=env/qa.tfvars.
# Committed, so never put secrets here. image_tag comes from the workflow input.

environment = "qa"

agent_model      = "bedrock"
bedrock_model_id = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"

# CORS origins the agent API accepts (never "*").
allowed_origins = "https://example.com"

# Empty serves HTTP on port 80. Set an ACM certificate ARN in eu-west-2 for HTTPS on 443.
acm_certificate_arn = ""

task_cpu            = 512
task_memory         = 1024
agent_desired_count = 1
mcp_desired_count   = 1
