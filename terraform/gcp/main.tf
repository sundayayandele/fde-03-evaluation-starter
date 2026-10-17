# Lab deployment on GCP: Artifact Registry, Cloud Run (scale to zero), Secret Manager,
# a dedicated service account, and an optional billing budget.
# Two-step apply: first with deploy_app=false, push the image, then deploy_app=true.
# Destroy at the end of every lab: `make tf-gcp-destroy`.

data "google_project" "this" {}

resource "google_project_service" "apis" {
  for_each           = toset(["run.googleapis.com", "artifactregistry.googleapis.com", "secretmanager.googleapis.com", "billingbudgets.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = var.app_name
  format        = "DOCKER"
  description   = "FDE series images"
  depends_on    = [google_project_service.apis]
}

resource "google_service_account" "run" {
  account_id   = "${var.app_name}-run"
  display_name = "Cloud Run runtime for ${var.app_name}"
}

resource "google_secret_manager_secret" "mistral" {
  secret_id = "${var.app_name}-mistral-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "mistral" {
  secret      = google_secret_manager_secret.mistral.id
  secret_data = var.mistral_api_key
}

resource "google_secret_manager_secret_iam_member" "run_reads_secret" {
  secret_id = google_secret_manager_secret.mistral.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.run.email}"
}

resource "google_cloud_run_v2_service" "app" {
  count               = var.deploy_app ? 1 : 0
  name                = var.app_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.run.email
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}/${var.app_name}:${var.image_tag}"
      ports {
        container_port = 8000
      }
      resources {
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }
      env {
        name  = "ENVIRONMENT"
        value = "gcp"
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
        name = "MISTRAL_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.mistral.secret_id
            version = "latest"
          }
        }
      }
      startup_probe {
        http_get {
          path = "/health/live"
        }
      }
      liveness_probe {
        http_get {
          path = "/health/live"
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.run_reads_secret, google_secret_manager_secret_version.mistral]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.deploy_app && var.allow_public ? 1 : 0
  name     = google_cloud_run_v2_service.app[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_billing_budget" "lab" {
  count           = var.billing_account == "" ? 0 : 1
  billing_account = var.billing_account
  display_name    = "${var.app_name}-monthly"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.5, 0.8, 1.0]
    content {
      threshold_percent = threshold_rules.value
    }
  }

  depends_on = [google_project_service.apis]
}
