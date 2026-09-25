output "ecr_repository_url" {
  description = "Push the container image here before applying services."
  value       = aws_ecr_repository.app.repository_url
}

output "aws_region" {
  description = "Region the stack is deployed in."
  value       = var.aws_region
}

output "alb_dns_name" {
  description = "Public hostname for the agent API."
  value       = aws_lb.agent.dns_name
}

output "agent_endpoint" {
  description = "Base URL for the agent API."
  value       = var.acm_certificate_arn == "" ? "http://${aws_lb.agent.dns_name}" : "https://${aws_lb.agent.dns_name}"
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "agent_api_key_secret_arn" {
  description = "Retrieve the value with: aws secretsmanager get-secret-value --secret-id <arn>."
  value       = aws_secretsmanager_secret.agent_api_key.arn
}
