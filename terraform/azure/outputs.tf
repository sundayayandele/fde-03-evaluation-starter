output "registry_login_server" {
  description = "Push the image here: az acr login -n <name>; docker push <server>/fde-03-evaluation:<tag>"
  value       = azurerm_container_registry.lab.login_server
}

output "registry_name" {
  value = azurerm_container_registry.lab.name
}

output "app_url" {
  description = "Public HTTPS URL of the Container App (after deploy_app=true)"
  value       = var.deploy_app ? "https://${azurerm_container_app.app[0].ingress[0].fqdn}" : "not deployed yet"
}
