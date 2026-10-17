output "ecr_repository_url" {
  description = "Push the image here: docker tag fde-03-evaluation:local <url>:<tag> && docker push <url>:<tag>"
  value       = aws_ecr_repository.app.repository_url
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "secret_arn" {
  description = "Set the value once: aws secretsmanager put-secret-value --secret-id <arn> --secret-string '{\"MISTRAL_API_KEY\":\"...\"}'"
  value       = aws_secretsmanager_secret.llm.arn
}

output "find_public_ip" {
  description = "Command that prints the task's public IP for the smoke test"
  value       = "aws ecs list-tasks --cluster ${aws_ecs_cluster.this.name} --query 'taskArns[0]' --output text | xargs -I{} aws ecs describe-tasks --cluster ${aws_ecs_cluster.this.name} --tasks {} --query \"tasks[0].attachments[0].details[?name=='networkInterfaceId'].value\" --output text | xargs -I{} aws ec2 describe-network-interfaces --network-interface-ids {} --query 'NetworkInterfaces[0].Association.PublicIp' --output text"
}
