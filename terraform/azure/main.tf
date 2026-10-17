# Lab deployment on Azure: Container Registry, Container Apps (scale to zero),
# Log Analytics, Key Vault (RBAC) with a managed identity, and a monthly budget.
# Two-step apply: first with deploy_app=false, push the image, then deploy_app=true.
# Destroy at the end of every lab: `make tf-azure-destroy`.

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  compact_name = replace(var.app_name, "-", "")
}

resource "azurerm_resource_group" "lab" {
  name     = "rg-${var.app_name}"
  location = var.location
  tags     = { series = "fde", managed_by = "terraform" }
}

resource "azurerm_log_analytics_workspace" "lab" {
  name                = "log-${var.app_name}"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_registry" "lab" {
  name                = "acr${local.compact_name}${random_string.suffix.result}"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  sku                 = "Basic"
  admin_enabled       = false
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${var.app_name}"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.lab.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_key_vault" "lab" {
  name                       = "kv-${substr(local.compact_name, 0, 14)}${random_string.suffix.result}"
  location                   = azurerm_resource_group.lab.location
  resource_group_name        = azurerm_resource_group.lab.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  purge_protection_enabled   = false
  soft_delete_retention_days = 7
}

resource "azurerm_role_assignment" "kv_admin_self" {
  scope                = azurerm_key_vault.lab.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "kv_read_app" {
  scope                = azurerm_key_vault.lab.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_key_vault_secret" "mistral" {
  name         = "mistral-api-key"
  value        = var.mistral_api_key
  key_vault_id = azurerm_key_vault.lab.id
  depends_on   = [azurerm_role_assignment.kv_admin_self]
}

resource "azurerm_container_app_environment" "lab" {
  name                       = "cae-${var.app_name}"
  location                   = azurerm_resource_group.lab.location
  resource_group_name        = azurerm_resource_group.lab.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.lab.id
}

resource "azurerm_container_app" "app" {
  count                        = var.deploy_app ? 1 : 0
  name                         = var.app_name
  container_app_environment_id = azurerm_container_app_environment.lab.id
  resource_group_name          = azurerm_resource_group.lab.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.lab.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  secret {
    name                = "mistral-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.mistral.versionless_id
    identity            = azurerm_user_assigned_identity.app.id
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 0
    max_replicas = 2

    container {
      name   = "api"
      image  = "${azurerm_container_registry.lab.login_server}/${var.app_name}:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "ENVIRONMENT"
        value = "azure"
      }
      env {
        name  = "LLM_PROVIDER"
        value = "mistral"
      }
      env {
        name  = "TARGET_URL"
        value = var.target_url
      }
      env {
        name  = "RUNS_DIR"
        value = "/tmp/runs"
      }
      env {
        name        = "MISTRAL_API_KEY"
        secret_name = "mistral-api-key"
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health/live"
      }
      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health/ready"
      }
    }
  }

  depends_on = [azurerm_role_assignment.acr_pull, azurerm_role_assignment.kv_read_app]
}

resource "azurerm_consumption_budget_resource_group" "lab" {
  name              = "budget-${var.app_name}"
  resource_group_id = azurerm_resource_group.lab.id
  amount            = var.monthly_budget_usd
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThan"
      threshold_type = "Actual"
      contact_emails = [var.alert_email]
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}
