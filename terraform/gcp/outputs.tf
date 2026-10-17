output "image_repository" {
  description = "Push the image here: gcloud auth configure-docker <region>-docker.pkg.dev; docker push <repo>/fde-03-evaluation:<tag>"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}

output "app_url" {
  description = "Cloud Run URL (after deploy_app=true)"
  value       = var.deploy_app ? google_cloud_run_v2_service.app[0].uri : "not deployed yet"
}
