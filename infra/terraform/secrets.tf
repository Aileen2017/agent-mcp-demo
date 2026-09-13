resource "random_password" "api_key" {
  length  = 40
  special = false
}

resource "aws_secretsmanager_secret" "agent_api_key" {
  name        = "${var.project}-${var.environment}-agent-api-key"
  description = "X-API-Key required by the agent API."
}

# Generated once by Terraform. Rotate out-of-band and this resource will not overwrite it.
resource "aws_secretsmanager_secret_version" "agent_api_key" {
  secret_id     = aws_secretsmanager_secret.agent_api_key.id
  secret_string = random_password.api_key.result

  lifecycle {
    ignore_changes = [secret_string]
  }
}
