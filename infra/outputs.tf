output "url" {
  description = "Endereço público do painel."
  value       = "http://${aws_eip.painel.public_ip}"
}

output "endereco_ip" {
  description = "Endereço IP fixo da máquina."
  value       = aws_eip.painel.public_ip
}

output "instancia" {
  description = "Identificador da máquina, usado pelo pipeline no deploy."
  value       = aws_instance.painel.id
}

output "metrics_token" {
  description = "Token de /metrics, para o Prometheus. Veja com: terraform output -raw metrics_token"
  value       = random_password.metrics_token.result
  sensitive   = true
}
