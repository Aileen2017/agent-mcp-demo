output "ecr_repository_url" {
  description = "ECR repository for the shared Lambda image."
  value       = aws_ecr_repository.lambda.repository_url
}

output "agent_url" {
  description = "Public agent API. Send X-API-Key with each request."
  value       = aws_lambda_function_url.agent.function_url
}

output "flights_mcp_url" {
  description = "IAM-authenticated flight MCP endpoint. Only the agent role can call it."
  value       = "${trimsuffix(aws_lambda_function_url.flights.function_url, "/")}/mcp"
}

output "calendar_mcp_url" {
  description = "IAM-authenticated calendar MCP endpoint. Only the agent role can call it."
  value       = "${trimsuffix(aws_lambda_function_url.calendar.function_url, "/")}/mcp"
}

output "agent_api_key_secret_arn" {
  description = "Secrets Manager secret holding the agent X-API-Key."
  value       = aws_secretsmanager_secret.agent_api_key.arn
}
